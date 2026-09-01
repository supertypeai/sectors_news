# IDX News Pipeline

Cloud Run job replacing `.github/workflows/pipeline_idx.yaml`. Scrapes 21 IDX
news sources, scores and posts the results into the Supabase `idx_news` table,
then prunes rows older than 120 days.

Runs every four hours at **:15 past, UTC** — `15 */4 * * *`, unchanged from the
workflow.

Read `../README.md` first. Everything about state, secrets, the image and
failure recovery is shared with SGX and documented once there. What follows is
only what is specific to IDX.

## Shape of a run

```
python -m scraper_engine.pipeline main_idx --scrape-only
        ↓  checkpoint pushed to gs://sectors-news-pipeline-state/idx/data/
python -m scraper_engine.pipeline main_idx --process-only --batch N --batch-size 30
        ↓  once per batch, 20s apart
python -m scraper_engine.pipeline remove_outdated_news --table-name idx_news
```

`remove_outdated_news` takes no `--source-scraper` here: `idx` is its default,
which is also why the deleted rows land in `data/outdated_news.json` rather than
`outdated_news_idx.json`.

Files that must survive between runs:

| File | Why |
| --- | --- |
| `data/last_state.json` | `last_run_at`, the WIB watermark `main_idx` scrapes forward from |
| `data/idx/pipeline_filtered.json` | the work-list the batches consume |
| `data/idx/pipeline.json`, `pipeline_yesterday.json` | raw scrape and the previous window, used for dedup |
| `data/outdated_news.json` | append-only archive of pruned rows |

Read-only per run, but refreshed from Supabase on the 1st and 15th of the month
by `metadata.load_company_data_idx()` and therefore pushed back too:
`data/idx/companies.json`, `sectors_data.json`, `subsectors_data.json`,
`data/unique_tags.json`.

## Deploy

```bash
./deploy.sh      # build + push + deploy the job (safe to re-run)
./schedule.sh    # create/update the four-hourly trigger (once)
```

Manual run:

```bash
gcloud run jobs execute sectors-news-idx-job \
    --region=us-central1 --project=datasheet-398802
```

Resume after a processing crash — the workflow's `process_only` input, and the
**only** correct response to a failure that got past the scrape:

```bash
gcloud run jobs execute sectors-news-idx-job \
    --region=us-central1 --project=datasheet-398802 \
    --update-env-vars PROCESS_ONLY=1
```

Inspect what it remembers:

```bash
../common/state.sh idx          # watermark, work-list, archived runs
../common/state.sh idx runs
```

Logs:

```bash
gcloud run jobs executions list --job=sectors-news-idx-job \
    --region=us-central1 --project=datasheet-398802
```

## Knobs

Set on the job by `deploy.sh`; override per execution with `--update-env-vars`.

| Variable | Default | Notes |
| --- | --- | --- |
| `STATE_BUCKET` | `sectors-news-pipeline-state` | |
| `STATE_PREFIX` | `idx` | the job's own corner of the bucket |
| `BATCH_SIZE` | `30` | the workflow's `BATCH_SIZE=30` |
| `BATCH_PAUSE_SECONDS` | `20` | the workflow's `sleep 20` |
| `PROCESS_ONLY` | unset | `1` to skip scraping and work the stored work-list |

## Chrome

IDX is the reason the browser version is pinned. `scrape_bca_news.py` builds its
own `uc.Chrome` — with a proxy extension, so it is the one scraper that cannot
fall back to a plain HTTP fetch — and was the source of the workflow's
`chrome-version: '1586874'` hardcode. Both pipelines drive Selenium (seven SGX
scrapers use the shared `SeleniumScraper` driver too), but BCA is the one that
broke on a version bump, so test a Chrome bump against it first.
