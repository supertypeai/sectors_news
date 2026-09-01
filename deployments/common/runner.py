"""The shared body of the two news pipeline Cloud Run jobs.

`pipeline_idx/main.py` and `pipeline_sgx/main.py` are *configuration*: which
scraper command to call, which files the run produces, which table to prune.
Everything else — the state round-trip, the checkpoint, the batch loop — lives
here so the two jobs cannot drift apart the way two copies of a workflow file
do.

What this replaces
------------------
On GitHub Actions the runs committed `data/` back to `main`. That commit was
not bookkeeping: it is what made `data/last_state.json` (the incremental
watermark) and `data/<source>/<filename>_filtered.json` (the work-list) survive
to the next run. Cloud Run's filesystem is discarded when the task ends, so the
same job is done here by a GCS prefix:

    gs://<STATE_BUCKET>/<STATE_PREFIX>/data/...      <- the live state tree
    gs://<STATE_BUCKET>/<STATE_PREFIX>/archive/<id>/ <- one snapshot per run

The ordering is the part that matters, and it is the same ordering the workflow
used:

  1. pull the state tree over the copy baked into the image
  2. scrape, then **push the checkpoint before processing anything**
  3. process in batches, then prune outdated rows
  4. on success only, push the whole tree back

Step 2 is why a crash during processing never forces a re-scrape: the work-list
is already durable, so a re-run with PROCESS_ONLY=1 picks it up. Step 4 is
deliberately not `finally` — a failed run must leave the checkpoint standing as
the resume point rather than overwrite it with whatever half-state the crash
left behind. That mirrors the workflow, where the final commit step simply did
not run if processing failed.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from google.cloud import storage

# The scraper reads and writes `./data/...` — relative to the process CWD, not
# to its own __file__ (see scraper_engine.database.metadata.DATA_DIR). So the
# job has to run from the application root and nowhere else.
APP_ROOT = Path(os.environ.get("APP_ROOT", "/app"))
DATA_DIR = APP_ROOT / "data"

# The per-market subdirectories of data/. Both jobs ship both, because both
# images are built from the same repo; each job pushes back only its own.
SOURCE_DIRS = ("idx", "sgx")

log = logging.getLogger("pipeline")


@dataclass(frozen=True)
class Pipeline:
    """Everything that differs between the IDX and SGX jobs."""

    source: str  # "idx" | "sgx" — also the typer command suffix and the data/ subdir
    filename: str  # --filename the scraper writes under data/<source>/
    table_name: str  # Supabase table the batches post into and the cleanup prunes

    # Written by the scrape half; pushed *before* processing starts. Exactly the
    # paths the workflow's "Checkpoint ingestion data" step git-added.
    checkpoint: tuple[str, ...]

    # Snapshotted to archive/<run id>/ on every run, success or failure — the
    # replacement for actions/upload-artifact's `if: always()`.
    artifacts: tuple[str, ...]

    # Extra argv for `remove_outdated_news` (SGX needs --source-scraper).
    cleanup_args: tuple[str, ...] = ()

    @property
    def command(self) -> str:
        return f"main_{self.source}"

    @property
    def work_list(self) -> Path:
        return DATA_DIR / self.source / f"{self.filename}_filtered.json"


def _env(name: str, default: str | None = None) -> str:
    value = os.environ.get(name) or default
    if value is None:
        raise SystemExit(f"Missing required environment variable: {name}")
    return value


def _env_int(name: str, default: int) -> int:
    return int(os.environ.get(name) or default)


def _env_flag(name: str) -> bool:
    return (os.environ.get(name) or "").strip().lower() in {"1", "true", "yes", "on"}


class State:
    """The `data/` tree, mirrored under one prefix of the state bucket.

    Each job owns its own prefix. That is not just tidiness: the workflows
    shared a `concurrency: news-data-pipeline` group with `queue: max`, and the
    only thing they actually contended over was pushing `data/` to the same
    branch. With a prefix each there is nothing to serialise, which is why the
    two Cloud Run jobs are free to overlap.
    """

    def __init__(self, bucket: str, prefix: str):
        self.bucket_name = bucket
        self.prefix = prefix.strip("/")
        self._bucket = storage.Client().bucket(bucket)
        self._root = f"{self.prefix}/data/"

    @property
    def uri(self) -> str:
        return f"gs://{self.bucket_name}/{self._root}"

    def pull(self) -> None:
        """Overlay the stored tree onto the copy baked into the image.

        Objects that do not exist yet simply leave the baked-in file in place,
        so a first run works off the repo's committed `data/` and a later run
        works off the last successful one. Nothing is deleted locally: the
        read-only reference files (companies.json, sectors_data.json,
        unique_tags.json) survive either way.
        """
        pulled = 0
        for blob in self._bucket.list_blobs(prefix=self._root):
            relative = blob.name[len(self._root) :]
            if not relative or relative.endswith("/"):
                continue
            destination = DATA_DIR / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            blob.download_to_filename(destination)
            pulled += 1

        log.info("state: pulled %d object(s) from %s", pulled, self.uri)

    def push(self, relatives: tuple[str, ...]) -> None:
        for relative in relatives:
            path = APP_ROOT / relative
            if not path.exists():
                log.warning("state: %s does not exist, not pushing it", relative)
                continue
            # Paths are given repo-relative ("data/idx/pipeline.json") to match
            # the workflow verbatim; the bucket layout drops the leading "data/"
            # because the prefix already carries it.
            self._bucket.blob(self._root + str(path.relative_to(DATA_DIR))).upload_from_filename(path)
            log.info("state: pushed %s", relative)

    def push_tree(self, source: str) -> None:
        """The `git add -A` equivalent: everything under data/ this job owns.

        Being literal about "everything" is the point, because two files are
        written by the run in ways that are easy to forget: `remove_outdated_news`
        appends to `data/outdated_news*.json`, and on the 1st and 15th of the
        month `metadata.load_company_data_*` refreshes `companies.json` from
        Supabase. Both were carried by the workflow's final `git add -A` and both
        would be silently lost to a targeted push.

        The one exclusion is the sibling market's directory. Both images are
        built from the same repo, so data/ always carries idx/ *and* sgx/;
        without this the IDX job would upload an untouched copy of data/sgx/ to
        idx/data/sgx/ on every run — harmless, since neither job reads the
        other's files, but ~250 KB of noise per run and a bucket that looks like
        it holds two copies of the truth.

        Root-level files are never excluded, including `last_state_sgx.json` and
        `outdated_news_sgx.json` sitting in the IDX prefix. Filtering those would
        mean guessing ownership from a filename, and guessing wrong loses a file.
        """
        pushed = 0
        for path in sorted(DATA_DIR.rglob("*")):
            if path.is_dir() or "__pycache__" in path.parts:
                continue

            relative = path.relative_to(DATA_DIR)

            if relative.parts[0] in SOURCE_DIRS and relative.parts[0] != source:
                continue

            self._bucket.blob(self._root + str(relative)).upload_from_filename(path)
            pushed += 1

        log.info("state: pushed %d object(s) to %s", pushed, self.uri)

    def archive(self, relatives: tuple[str, ...], run_id: str) -> None:
        for relative in relatives:
            path = APP_ROOT / relative
            if not path.exists():
                continue
            destination = f"{self.prefix}/archive/{run_id}/{path.relative_to(DATA_DIR)}"
            self._bucket.blob(destination).upload_from_filename(path)

        log.info(
            "state: archived run to gs://%s/%s/archive/%s/",
            self.bucket_name,
            self.prefix,
            run_id,
        )


def _scraper(*args: str) -> None:
    """Run one scraper command, streaming its output to the task log.

    A subprocess per invocation, not an in-process call. Two reasons, both
    load-bearing: the commands are `typer` entry points whose defaults are
    `OptionInfo` sentinels rather than values, so calling them as functions
    silently passes the wrong arguments; and a fresh interpreter per batch is
    what the workflow did, which matters for a run that holds Chrome and a pool
    of LLM clients open.
    """
    command = [sys.executable, "-m", "scraper_engine.pipeline", *args]
    log.info("+ %s", " ".join(command))
    subprocess.run(command, cwd=APP_ROOT, check=True)


def _run_id() -> str:
    # Cloud Run sets these on every task; the timestamp is the local fallback.
    execution = os.environ.get("CLOUD_RUN_EXECUTION")
    if execution:
        return execution
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _work_list_size(path: Path) -> int:
    try:
        with path.open() as handle:
            return len(json.load(handle))
    except (FileNotFoundError, json.JSONDecodeError, TypeError) as error:
        log.warning("could not read work-list %s (%s); treating it as empty", path, error)
        return 0


def run(pipeline: Pipeline) -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        stream=sys.stdout,
    )

    state = State(_env("STATE_BUCKET"), _env("STATE_PREFIX", pipeline.source))
    batch_size = _env_int("BATCH_SIZE", 30)
    batch_pause = _env_int("BATCH_PAUSE_SECONDS", 20)
    process_only = _env_flag("PROCESS_ONLY")
    run_id = _run_id()

    log.info(
        "%s pipeline starting (run %s, process_only=%s, batch_size=%d)",
        pipeline.source.upper(),
        run_id,
        process_only,
        batch_size,
    )

    state.pull()

    try:
        if not process_only:
            _scraper(pipeline.command, "--scrape-only")

            # Before a single article is processed. A crash after this point is
            # recoverable; a crash before it costs only the scrape, because the
            # advanced watermark in last_state.json has not been pushed either.
            state.push(pipeline.checkpoint)

        total = _work_list_size(pipeline.work_list)
        batches = -(-total // batch_size)  # ceil
        log.info("work-list: %d article(s) -> %d batch(es)", total, batches)

        for batch in range(1, batches + 1):
            log.info("=== B%d ===", batch)
            _scraper(
                pipeline.command,
                "--process-only",
                "--batch",
                str(batch),
                "--batch-size",
                str(batch_size),
            )
            time.sleep(batch_pause)

        log.info("=== CLEANUP ===")
        _scraper("remove_outdated_news", "--table-name", pipeline.table_name, *pipeline.cleanup_args)

    except subprocess.CalledProcessError as error:
        state.archive(pipeline.artifacts, run_id)
        log.error(
            "step failed with exit code %d. The checkpoint in %s is intact — "
            "resume with PROCESS_ONLY=1 rather than letting the next scheduled "
            "run re-scrape, which would overwrite the work-list.",
            error.returncode,
            state.uri,
        )
        raise SystemExit(1) from error

    state.archive(pipeline.artifacts, run_id)
    state.push_tree(pipeline.source)
    log.info("%s pipeline ok (run %s)", pipeline.source.upper(), run_id)
