# Build context is the REPO ROOT, not this directory — the image needs src/,
# data/ and deployments/common/, so the context has to be the repo and the build
# is driven by cloudbuild.yaml.
#
#   docker build -f deployments/pipeline_sgx/Dockerfile .    (from the root)
#
# This is byte-identical to deployments/pipeline_idx/Dockerfile apart from the
# main.py it copies, and that is on purpose: the two jobs get separate images so
# an IDX-only change cannot take SGX down with it. The shared logic lives in
# runner.py, which both copy.

# ── build ───────────────────────────────────────────────────────────────
FROM python:3.12-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/
WORKDIR /app

# README.md is not documentation here — pyproject declares `readme = "README.md"`
# and the build fails without it.
COPY pyproject.toml uv.lock README.md ./

# uv.lock records this project as `source = { virtual = "." }` (pyproject has no
# [build-system]), so `uv sync` installs the dependencies and not the project.
# That is why the runtime stage sets PYTHONPATH to /app/src instead of relying
# on an installed package — the CI equivalent of the workflow's `uv pip install -e .`.
RUN uv sync --frozen --no-dev

# The GCS client for the state round-trip. --no-deps deliberately: google-auth,
# google-api-core and requests are already in the locked set (langchain-google-genai
# pulls the first two), and letting a resolver near them risks moving a pin that
# the scrapers depend on. These four are the whole remaining closure.
RUN uv pip install --no-deps \
    google-cloud-storage google-cloud-core google-resumable-media google-crc32c

# ── runtime ─────────────────────────────────────────────────────────────
FROM python:3.12-slim
WORKDIR /app

COPY --from=builder /app/.venv /app/.venv

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH=/app/src \
    PYTHONUNBUFFERED=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# tzdata is not optional: the pipeline resolves ZoneInfo("Asia/Jakarta") to
# derive the scrape window, and python:3.12-slim ships no zoneinfo database, so
# without it the run dies on ZoneInfoNotFoundError before it scrapes anything.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl unzip tzdata fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

# `scrapling install` == `playwright install chromium` + `install-deps chromium`
# + a TLD-list refresh. Scrapling's Fetcher/DynamicFetcher tiers in
# preprocessing/article_fetcher.py need the Chromium it downloads. install-deps
# is also the maintained list of shared libraries a headless browser needs on
# Debian, so running it before Chrome is installed means Chrome's dependencies
# are already satisfied.
RUN apt-get update \
    && scrapling install \
    && rm -rf /var/lib/apt/lists/*

# Chrome for Testing, pinned. The workflow pinned browser-actions/setup-chrome to
# Chromium snapshot 1586874 ("hardcode chrome version", to keep the BCA Sekuritas
# scraper working); that snapshot is a 147.x dev build. This is the last stable
# 147 release — same major, which is what undetected_chromedriver matches on via
# version_main, but an actual release rather than a main-branch snapshot.
#
# Bumping this is the same decision as bumping the pin in the workflow was:
# check scrape_bca_news.py still works before you do it.
ARG CHROME_VERSION=147.0.7727.117
RUN CFT="https://storage.googleapis.com/chrome-for-testing-public/${CHROME_VERSION}/linux64" \
    && curl -fsSL -o /tmp/chrome.zip "${CFT}/chrome-linux64.zip" \
    && curl -fsSL -o /tmp/chromedriver.zip "${CFT}/chromedriver-linux64.zip" \
    && unzip -q /tmp/chrome.zip -d /opt \
    && unzip -q /tmp/chromedriver.zip -d /opt \
    && rm /tmp/chrome.zip /tmp/chromedriver.zip \
    # base.scraper.get_chrome_info() finds the browser by shutil.which("google-chrome")
    # and parses `--version`, so the name of this symlink is load-bearing.
    && ln -s /opt/chrome-linux64/chrome /usr/local/bin/google-chrome \
    && ln -s /opt/chromedriver-linux64/chromedriver /usr/local/bin/chromedriver \
    && google-chrome --version

COPY src ./src

# Not just reference data. data/ is the first-run seed for the state tree, and
# companies.json / sectors_data.json / subsectors_data.json / unique_tags.json
# are read on every run by scraper_engine.database.metadata. The live copies are
# pulled over these from GCS at startup — see runner.State.pull.
COPY data ./data

COPY deployments/common/runner.py ./runner.py
COPY deployments/pipeline_sgx/main.py ./main.py

CMD ["python", "main.py"]
