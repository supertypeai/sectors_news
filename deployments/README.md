# Cloud Run deployments

The two news pipelines, moved off GitHub Actions onto Cloud Run jobs in
**`datasheet-398802`** (project number 607838700058), region **`us-central1`**
at 2 vCPU / 4 GiB.

| GitHub workflow | Cloud Run job | Scheduler job | Schedule (UTC) |
| --- | --- | --- | --- |
| `.github/workflows/pipeline_idx.yaml` | `sectors-news-idx-job` | `sectors-news-idx-4hourly` | `15 */4 * * *` |
| `.github/workflows/pipeline_sgx.yaml` | `sectors-news-sgx-job` | `sectors-news-sgx-4hourly` | `0 */4 * * *` |

```
deployments/
├── common/
│   ├── config.sh      # project, region, bucket, accounts, runtime value names
│   ├── bootstrap.sh   # one-time: APIs, registry, bucket, service account, IAM
│   ├── state.sh       # read-only view of what the pipelines remember
│   └── runner.py      # the shared job body — scrape → checkpoint → batch → prune
├── pipeline_idx/      # Dockerfile, cloudbuild.yaml, main.py, deploy.sh, schedule.sh
└── pipeline_sgx/      # the same, for SGX
```

`main.py` in each deployment is configuration — which command, which files,
which table. The sequence itself lives once, in `runner.py`, because two copies
of a workflow file is exactly how the two pipelines were drifting.

## First-time setup

`.env` at the repo root supplies the five runtime values — it is gitignored and
excluded from the build context, so it never reaches the image. `deploy.sh`
reads it on every deploy (`ENV_FILE=/path/to/env` to point elsewhere).

```bash
gcloud config set project datasheet-398802

deployments/common/bootstrap.sh --seed

deployments/pipeline_idx/deploy.sh && deployments/pipeline_idx/schedule.sh
deployments/pipeline_sgx/deploy.sh && deployments/pipeline_sgx/schedule.sh
```

`bootstrap.sh` is idempotent and safe to re-run. It enables `iam` (the only API
this project was missing), reuses the `cloud-run-source-deploy` registry that
already exists in `us-central1`, creates the state bucket there with its
retention rule, and creates the `sectors-news-pipeline` service account with
`storage.objectAdmin` **on the bucket** — the only IAM binding this setup needs.

No project-level binding is required, which matters because `roles/editor`
cannot make one:

- **`roles/run.invoker`** is not granted. Cloud Scheduler triggers the jobs as
  `SCHEDULER_SA`, the default compute account, which already holds
  `roles/editor` — and `roles/editor` includes `run.jobs.run`.
- **`roles/secretmanager.secretAccessor`** is not granted, because nothing uses
  Secret Manager. See the Secrets section below.

Redeploy after a code change with just `deploy.sh`; `schedule.sh` is a one-off.
Rotating a value means editing `.env` and re-running `deploy.sh`.

## State: what replaced the git commits

On GitHub, every run committed `data/` back to `main`. That was not bookkeeping.
It is what made two things survive to the next run:

- **`data/last_state.json`** — the incremental watermark. `main_idx` reads
  `last_run_at` from it to decide how far back to scrape.
- **`data/<source>/<filename>_filtered.json`** — the work-list the processing
  half consumes.

Cloud Run discards the filesystem when a task ends, so a GCS prefix does that
job now:

```
gs://sectors-news-pipeline-state/
├── idx/
│   ├── data/…              # the live state tree (the old `git add -A`)
│   └── archive/<run id>/…   # one snapshot per run (the old upload-artifact)
└── sgx/
    ├── data/…
    └── archive/<run id>/…
```

The order is the same order the workflow used, and the order is the point:

1. **Pull** the state tree over the copy baked into the image. A missing object
   leaves the image's committed copy in place, so a first run works.
2. **Scrape**, then push the checkpoint — `pipeline*.json`, the filtered
   work-list, `last_state*.json` — *before processing anything*.
3. **Process** in batches of 30 with a 20-second pause, then
   `remove_outdated_news`.
4. On success only, push the whole `data/` tree back.

Step 2 is why a crash during processing never forces a re-scrape. Step 4 is
deliberately not a `finally`: a failed run has to leave the checkpoint standing
as the resume point rather than overwrite it with whatever half-state the crash
produced. That mirrors the workflow, where the final commit step simply did not
run when processing failed.

Each job owns its own prefix, and that is what retired the
`concurrency: news-data-pipeline` group with `queue: max`. The only thing the
two workflows actually contended over was pushing `data/` to the same branch.
With a prefix and a Supabase table each, an overlap now costs nothing.

**The repo's `data/` is no longer updated by the pipelines.** It is the seed and
the reference data; the bucket is the record.

## Looking at the state

On GitHub you could see the pipeline's memory by opening the repo. The bucket is
tidier but invisible, so `common/state.sh` is the replacement for "just look at
it". Read-only — it never writes to the bucket.

```bash
deployments/common/state.sh                 # both pipelines, at a glance
deployments/common/state.sh idx             # one pipeline, in full
deployments/common/state.sh idx runs        # recently archived runs
deployments/common/state.sh idx get last_state.json
deployments/common/state.sh idx get idx/pipeline_filtered.json
deployments/common/state.sh idx get last_state.json --run 20260901T072003Z
```

The summary is the thing to check after a run:

```
IDX  gs://sectors-news-pipeline-state/idx/
  watermark      2026-09-01T14:15:03+07:00  (4.2 hours ago)
  work-list      63 articles   188 KiB  2026-09-01 07:20:03
  runs archived  37   latest 20260901T072003Z
```

A watermark much older than four hours means runs are failing or not firing. A
work-list that never changes size means the scrape half is not running.

## Recovering a failed run

This is the part worth knowing before you need it. The watermark advances at
*scrape* time, so a run that scrapes successfully and then dies in processing has
already claimed those articles. The next scheduled run will scrape from the new
watermark, find nothing, and **overwrite the work-list with an empty list** —
losing the articles the failed run had queued.

So a processing failure is resumed, not retried:

```bash
gcloud run jobs execute sectors-news-idx-job \
    --region=us-central1 --project=datasheet-398802 \
    --update-env-vars PROCESS_ONLY=1
```

That is the `workflow_dispatch` input `process_only` from the workflow, and it
has to happen before the next four-hourly firing.

The same reasoning is why both jobs are deployed with `--max-retries=0`. A Cloud
Run retry restarts the container from scratch — which means it re-scrapes, which
means it destroys the work-list. Do not raise it.

## Secrets — passed as environment variables, not Secret Manager

The five values `scraper_engine.config.conf` demands are read from **`.env` at
the repo root** at deploy time and handed to Cloud Run as plain environment
variables:

```
SUPABASE_URL  SUPABASE_KEY  OPENROUTER_API_KEY  GROQ_API_KEY_DEV  PROXY
```

`write_env_file` in `common/config.sh` builds a mode-0600 temp file containing
these plus the runtime config (`STATE_BUCKET`, `STATE_PREFIX`, `BATCH_SIZE`,
`BATCH_PAUSE_SECONDS`) and passes it as `--env-vars-file`. The file is deleted
on exit, including on failure. A missing or empty value aborts the deploy rather
than producing a job that fails at import.

A file rather than `--set-env-vars` for two reasons: command-line arguments are
visible to `ps` for every user on the machine, and a value containing a comma
would silently split on the delimiter. Values are YAML double-quoted with
backslashes and quotes escaped.

**Why not Secret Manager.** Reading a mounted secret needs
`roles/secretmanager.secretAccessor`. Granting it needs a project-level IAM
binding, and `roles/editor` has neither `resourcemanager.projects.setIamPolicy`
nor `secretmanager.secrets.setIamPolicy`. `roles/editor` also does not include
`secretmanager.versions.access`, so running the job as some existing
editor-holding account is not a way around it either.

**What that trades away:** anyone with `run.jobs.get` on this project can read
these values back with `gcloud run jobs describe`. There are four
editor-holding accounts here. GitHub Actions secrets are masked; these are not.

**To switch back**, once an owner has run:

```bash
gcloud projects add-iam-policy-binding datasheet-398802 \
    --member "serviceAccount:sectors-news-pipeline@datasheet-398802.iam.gserviceaccount.com" \
    --role roles/secretmanager.secretAccessor
```

…create one secret per name, and in each `deploy.sh` replace
`--env-vars-file "$ENV_VARS_FILE"` with `--set-env-vars` for the four config
values plus `--set-secrets "SUPABASE_URL=SUPABASE_URL:latest,…"`.

`DATABASE_URL`, `DB_KEY` and `OPENAI_API_KEY` were **not** carried over, and the
five Groq / three Gemini keys the workflows passed are gone from `src/` as of
`1ddebc7 refactor(llm): centralize model configuration`. Keep `SECRETS` in
`config.sh` in step with `grep get_required_env src/scraper_engine/config/conf.py`.

## The image

Both jobs ship the same three browser stacks the runners had:

- **Chrome for Testing 147.0.7727.117**, symlinked to `/usr/local/bin/google-chrome`
  because `base/scraper.py:get_chrome_info()` finds it by that name. The workflow
  pinned `browser-actions/setup-chrome` to Chromium snapshot `1586874` to keep
  the BCA Sekuritas scraper working; that snapshot is a 147.x dev build, so this
  is the same major as a real release. Bumping it is the same decision bumping
  the workflow pin was.
- **Chromium via `scrapling install`**, for the `Fetcher` / `DynamicFetcher`
  tiers in `preprocessing/article_fetcher.py`.
- **`tzdata`**, which `python:3.12-slim` does not ship and
  `ZoneInfo("Asia/Jakarta")` needs.

`undetected_chromedriver` still downloads its own driver at runtime, as it did on
the runners, because `scrape_bca_news.py` has `driver_executable_path` commented
out. The image installs a matching `chromedriver` anyway; uncommenting that line
would turn a per-run network dependency into a build-time one.

`uv.lock` records the project as `source = { virtual = "." }` — there is no
`[build-system]` in `pyproject.toml`, so `uv sync` installs the dependencies and
not the project. The image sets `PYTHONPATH=/app/src` instead, which is what the
workflow's `uv pip install -e .` was achieving.

## What a run costs

Measured from 30 successful Actions runs each, job-level, queue time excluded:

| | median | mean | p90 | max |
| --- | --- | --- | --- | --- |
| IDX | 37 min | 57 min | 153 min | 190 min |
| SGX | 8.5 min | 8.4 min | 15 min | 20 min |

One sampled 157-minute IDX run breaks down as **31 min scraping** (537 raw
articles from 21 sources) and **124 min processing** 269 articles at 27 s each,
of which 185 were dropped by the score gate and 80 reached Supabase. Only 6% of
the run is the deliberate `sleep(5)` / `sleep(20)` pauses — the rest is waiting
on page loads and LLM APIs, not CPU. The article loop is sequential and
single-threaded; Chrome and Chromium are what actually consume the cores.

At 6 runs/day that is **~196 hours of billed task time per month**. Cloud Run
bills the whole task duration, so waiting on an LLM costs the same as computing.

`us-central1` is a **Tier 1** region: $0.000024/vCPU-s and $0.0000025/GiB-s.
Both `asia-southeast1` and `asia-southeast2` are Tier 2 ($0.00003360 and
$0.00000350), so staying in the region would have cost ~37% more for identical
compute. The bucket and the registry sit in `us-central1` too, so nothing
crosses a region boundary.

| config | monthly |
| --- | --- |
| **2 vCPU / 4 GiB, us-central1** (deployed) | **~$38** |
| 1 vCPU / 2 GiB, us-central1 | ~$17 |
| 2 vCPU / 4 GiB, asia-southeast2 (Tier 2) | ~$52 |
| GitHub Actions, private repo | ~$59 |
| GitHub Actions, public repo | $0 |

**The repo is public today, so Actions currently costs $0.** The comparison
above is against the private repo you are moving to, not against today.

Fixed costs are ~$2/month of that: Secret Manager ($0.78 for 13 secrets),
Artifact Registry ($0.58 for two ~3 GB images), Cloud Build (~$0.60), GCS
(~$0.11). Cloud Scheduler is free under its 3-job allowance.

Two things that are easy to miss:

- **The sizing is a starting point, not a measurement.** The only configuration
  this pipeline is *known* to run on is a GitHub public-repo runner: 4 vCPU /
  16 GiB. 2 vCPU / 4 GiB is already a 2x CPU and 4x memory cut from that, chosen
  rather than measured. Halving again to 1 vCPU / 2 GiB would save ~$21/month but
  is an 8x memory cut from the proven baseline, and an OOM is a SIGKILL
  mid-processing that needs a manual `PROCESS_ONLY` resume. Watch the container
  utilization metrics for a few runs before going lower.
- **The scrapers now run from a US datacenter IP.** Four of the five tiers in
  `get_article_body` go direct; `PROXY` is only the last resort. If an Indonesian
  or Singaporean source starts returning nothing, `REGION` in `common/config.sh`
  is the first thing to reconsider.
- **Cloud Scheduler is more reliable than GitHub's cron.** Actions actually
  delivered 5.24 runs/day against a 6/day schedule. Moving to Cloud Run means
  ~15% more runs, so ~15% more compute *and* ~15% more LLM spend. The Groq /
  Gemini / OpenAI bill is not on either platform's invoice and is plausibly
  larger than both.

## Other caveats

- The `archive/` prefixes have a 60-day delete rule, matching the workflow's
  `retention-days: 60`. It is scoped by prefix so it can never reach the live
  state tree.
- **`data/outdated_news.json` grows without bound** (8.7 MB today).
  `remove_outdated_news` appends every pruned row to it and nothing ever
  truncates it. It is pushed on every run and included in every archive
  snapshot. That predates this migration, but it is now a storage line item —
  worth truncating or moving to a table at some point.
- The `.gcloudignore` matters: without it `gcloud builds submit` falls back to
  `.gitignore` and uploads the 684 MB `.venv/`.

## Turning the workflows off

Once both jobs have run cleanly, delete `.github/workflows/pipeline_idx.yaml`
and `pipeline_sgx.yaml` — or comment out their `schedule:` blocks and keep
`workflow_dispatch` for a while. Do not leave both firing: the Action would keep
committing a `data/` that the Cloud Run jobs no longer read, which reads as a
working pipeline while telling you nothing about the one that is actually
running.
