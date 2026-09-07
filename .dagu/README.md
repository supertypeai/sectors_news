# Dagu workflows

The two news pipelines as [Dagu](https://dagu.sh) DAGs, deployed by
[runners](https://github.com/supertypeai/runners) — the app that reads
`.dagu/<name>/workflow.yaml` out of this repository, composes each into a DAG
and registers it over Dagu's REST API.

| Directory | DAG | Schedule (UTC) | Replaces |
| --- | --- | --- | --- |
| `idx-news-pipeline/` | `sectors_news--idx-news-pipeline` | `15 */4 * * *` | `.github/workflows/pipeline_idx.yaml` |
| `sgx-news-pipeline/` | `sectors_news--sgx-news-pipeline` | `0 */4 * * *` | `.github/workflows/pipeline_sgx.yaml` |
| `idx-news-resume/` | `sectors_news--idx-news-resume` | manual | that workflow's `process_only` input |
| `sgx-news-resume/` | `sectors_news--sgx-news-resume` | manual | the same, for SGX |

```
.dagu/
├── Dockerfile              the runtime image — dependencies and browsers, no code
├── steps/
│   ├── preflight.sh
│   ├── commit.sh           checkpoint | publish
│   └── process.sh
└── <name>/workflow.yaml    configuration: which command, which files, which table
```

Each `workflow.yaml` is configuration and nothing else — the YAML spelling of
`runner.Pipeline` in `deployments/common/runner.py`.

**This does not retire the Cloud Run jobs.** Both are driven by the same
four-hourly cron and both would scrape the same window, pay for the same LLM
calls and race to insert. Pause the Cloud Scheduler jobs before deploying these:

```bash
gcloud scheduler jobs pause sectors-news-idx-4hourly --location=us-central1 --project=datasheet-398802
gcloud scheduler jobs pause sectors-news-sgx-4hourly --location=us-central1 --project=datasheet-398802
```

## State is git again

Cloud Run replaced the workflows' `data/` commits with a GCS prefix because its
filesystem is discarded when a task ends. Under runners the container has a
`GITHUB_TOKEN`, so the pipelines are back to the original arrangement: **the
commit is the state.**

- `data/last_state.json` — the incremental watermark, read by `main_idx` to
  decide how far back to scrape.
- `data/<market>/*_filtered.json` — the work-list the processing half consumes.

The order matters more than the mechanism, and it is the workflows' order:

1. `scrape` builds the work-list and advances the watermark.
2. `checkpoint` commits and pushes both, *before a single article is processed*.
3. `process` works through the list in batches of 30, then prunes.
4. `publish` commits the whole of `data/` — **on success only**.

Step 2 is why a crash during processing never costs a re-scrape. Step 4 is
deliberately not an always-run step: a failed run has to leave the checkpoint
standing as the resume point rather than bury it under whatever half-state the
crash produced.

So `data/` in this repository is live again, written by `plumbersai[bot]` every
four hours. `deployments/README.md` calls it only a seed; that is true of the
Cloud Run jobs and no longer true of these.

## Recovering a failed run

**Do not press Retry on a failed pipeline run.** The watermark advances at
*scrape* time, so a run that scraped and then died in processing has already
claimed those articles. Retry re-runs the DAG from the top, scrapes from the new
watermark, finds nothing, and overwrites the work-list with an empty list.

Start `sectors_news--idx-news-resume` instead (or the SGX one), before the next
scheduled firing. It checks out `main` — the checkpoint commit — and runs
`process` and `publish` against it. Nothing in it scrapes, so it is safe to run
repeatedly; `processor.py` re-reads the already inserted `source` URLs out of
the table before each batch, so an article the failed run posted is skipped
rather than duplicated.

If it was `checkpoint` itself that failed there is nothing to resume: `main`
still holds the old watermark, so let the next scheduled run scrape that window
again.

## The runtime image

This repository cannot install its dependencies per run — a 717 MB virtualenv
over 180 packages, Playwright's Chromium and a pinned Chrome for Testing is
minutes of work and gigabytes of transfer every four hours. So the environment
is an image, built once on the runner host:

```bash
docker build -f .dagu/Dockerfile -t sectors-news-runtime:latest .
```

`pull_policy: never` in every workflow — the tag is local, and nothing will go
looking for it in a registry.

The image carries **no application code**. `src/` and `data/` come from the
checkout in `/workspace` and `PYTHONPATH` points there, so a code or data change
ships by pushing to `main`. **Only a dependency change needs a rebuild**, and
`preflight.sh` will not let you forget: it compares the `uv.lock` baked into the
image against the one just checked out and fails the run, before it scrapes, if
they differ. Rebuild while no run is active; the next run picks it up.

## What the host needs

Beyond a working runners installation, the five secrets that
`scraper_engine.config.conf` demands, at `/deploy` → the key icon on
`sectors_news`:

```
SUPABASE_URL  SUPABASE_KEY  OPENROUTER_API_KEY  GROQ_API_KEY_DEV  PROXY
```

`GITHUB_TOKEN` is not among them — runners mints and refreshes it.

Optionally **a queue**, if you want the two markets serialised the way GitHub
Actions serialised them through `concurrency: news-data-pipeline`. All four
workflows name that queue; the name does nothing until Dagu's own config defines
it, in `/etc/dagu/config.yaml` or `$DAGU_HOME/config.yaml`:

```yaml
queues:
  enabled: true
  config:
    - name: news-data-pipeline
      max_concurrency: 1
```

Without it the two may overlap, which costs nothing but a rebase — the schedules
are 15 minutes apart, the markets write disjoint files, and `commit.sh` retries
a lost race five times.

## Two things Dagu 2.16 forces

- **The steps call scripts rather than carrying their own.** A DAG-level
  `container:` turns a multi-line `run:` into a `script`, which the container
  action rejects, so single-line commands are the only option.
- **`/dev/shm` is bind-mounted from the host.** Chrome exhausts a container's
  default 64 MB partway through a page rather than at startup, and Dagu's
  container config has no `shm_size`. `preflight.sh` asserts the mount took.

And one runners constraint: the resume DAGs are separate DAGs rather than a
parameter, because runners owns `params:` — it uses them to pin the commit.
