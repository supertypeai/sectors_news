# SGX News Pipeline

Cloud Run job replacing `.github/workflows/pipeline_sgx.yaml`. Scrapes 12
Singapore news sources, scores and posts the results into the Supabase
`sgx_news` table, then prunes rows older than 120 days.

Runs every four hours **on the hour, UTC** — `0 */4 * * *`, unchanged from the
workflow, fifteen minutes ahead of IDX.

Read `../README.md` first. Everything about state, secrets, the image and
failure recovery is shared with IDX and documented once there. What follows is
only what is specific to SGX.

## Shape of a run

```
python -m scraper_engine.pipeline main_sgx --scrape-only
        ↓  checkpoint pushed to gs://sectors-news-pipeline-state/sgx/data/
python -m scraper_engine.pipeline main_sgx --process-only --batch N --batch-size 30
        ↓  once per batch, 20s apart
python -m scraper_engine.pipeline remove_outdated_news --table-name sgx_news --source-scraper sgx
```

That trailing `--source-scraper sgx` is the one argument that differs from IDX,
and it does two things: it selects the SGX scoring prompt criteria, and it sends
the pruned rows to `data/outdated_news_sgx.json` instead of the IDX file.

Files that must survive between runs:

| File | Why |
| --- | --- |
| `data/last_state_sgx.json` | `last_run_at`, the SGT watermark `main_sgx` scrapes forward from |
| `data/sgx/pipeline_sgx_filtered.json` | the work-list the batches consume |
| `data/sgx/pipeline_sgx.json`, `pipeline_sgx_yesterday.json` | raw scrape and the previous window, used for dedup |
| `data/outdated_news_sgx.json` | append-only archive of pruned rows |

Read-only per run, but refreshed from Supabase on the 1st and 15th of the month
by `metadata.load_company_data_sgx()` and therefore pushed back too:
`data/sgx/sgx_companies.json`, `sectors_data_sgx.json`,
`subsectors_data_sgx.json`, `data/unique_tags.json`.

Note the timezone: `main_sgx` resolves its window in `Asia/Singapore`, where
`main_idx` uses `Asia/Jakarta`. The schedule itself is UTC in both cases.

## Deploy

```bash
./deploy.sh      # build + push + deploy the job (safe to re-run)
./schedule.sh    # create/update the four-hourly trigger (once)
```

Manual run:

```bash
gcloud run jobs execute sectors-news-sgx-job \
    --region=us-central1 --project=datasheet-398802
```

Resume after a processing crash — the workflow's `process_only` input, and the
**only** correct response to a failure that got past the scrape:

```bash
gcloud run jobs execute sectors-news-sgx-job \
    --region=us-central1 --project=datasheet-398802 \
    --update-env-vars PROCESS_ONLY=1
```

Inspect what it remembers:

```bash
../common/state.sh sgx          # watermark, work-list, archived runs
../common/state.sh sgx runs
```

Logs:

```bash
gcloud run jobs executions list --job=sectors-news-sgx-job \
    --region=us-central1 --project=datasheet-398802
```

## Knobs

Set on the job by `deploy.sh`; override per execution with `--update-env-vars`.

| Variable | Default | Notes |
| --- | --- | --- |
| `STATE_BUCKET` | `sectors-news-pipeline-state` | |
| `STATE_PREFIX` | `sgx` | the job's own corner of the bucket |
| `BATCH_SIZE` | `30` | the workflow's `BATCH_SIZE=30` |
| `BATCH_PAUSE_SECONDS` | `20` | the workflow's `sleep 20` |
| `PROCESS_ONLY` | unset | `1` to skip scraping and work the stored work-list |

## Why the image is identical to IDX's

It is, apart from the `main.py` it copies — same Chrome pin, same Chromium, same
dependency tree. Separate images rather than one shared image so a change made
for one market cannot take the other down; the logic that would actually be
worth sharing already is, in `../common/runner.py`.
