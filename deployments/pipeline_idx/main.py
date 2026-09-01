"""IDX news pipeline — the Cloud Run replacement for `.github/workflows/pipeline_idx.yaml`.

Configuration only. The scrape → checkpoint → batch → prune sequence lives in
`runner.py`, shared with the SGX job so the two cannot drift.
"""

from runner import Pipeline, run

IDX = Pipeline(
    source="idx",
    filename="pipeline",
    table_name="idx_news",
    # The workflow's "Checkpoint ingestion data" step, path for path.
    checkpoint=(
        "data/idx/pipeline.json",
        "data/idx/pipeline_filtered.json",
        "data/idx/pipeline_yesterday.json",
        "data/last_state.json",
    ),
    # The workflow's "Save generated IDX data" upload-artifact step, path for path.
    artifacts=(
        "data/idx/pipeline.json",
        "data/idx/pipeline_filtered.json",
        "data/idx/pipeline_yesterday.json",
        "data/last_state.json",
        "data/outdated_news.json",
    ),
    # IDX is the default --source-scraper, so the cleanup takes no extra argv.
    cleanup_args=(),
)


if __name__ == "__main__":
    run(IDX)
