"""SGX news pipeline — the Cloud Run replacement for `.github/workflows/pipeline_sgx.yaml`.

Configuration only. The scrape → checkpoint → batch → prune sequence lives in
`runner.py`, shared with the IDX job so the two cannot drift.
"""

from runner import Pipeline, run

SGX = Pipeline(
    source="sgx",
    filename="pipeline_sgx",
    table_name="sgx_news",
    # The workflow's "Checkpoint ingestion data" step, path for path.
    checkpoint=(
        "data/sgx/pipeline_sgx.json",
        "data/sgx/pipeline_sgx_filtered.json",
        "data/sgx/pipeline_sgx_yesterday.json",
        "data/last_state_sgx.json",
    ),
    # The workflow's "Save generated SGX data" upload-artifact step, path for path.
    artifacts=(
        "data/sgx/pipeline_sgx.json",
        "data/sgx/pipeline_sgx_filtered.json",
        "data/sgx/pipeline_sgx_yesterday.json",
        "data/last_state_sgx.json",
        "data/outdated_news_sgx.json",
    ),
    # Unlike IDX, the cleanup has to be told which scraper it is pruning for —
    # it selects the score prompt criteria and the outdated_news_*.json name.
    cleanup_args=("--source-scraper", "sgx"),
)


if __name__ == "__main__":
    run(SGX)
