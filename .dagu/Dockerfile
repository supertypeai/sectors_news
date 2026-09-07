# Build context is the REPO ROOT:
#
#   docker build -f .dagu/Dockerfile -t sectors-news-runtime:latest .
#
# The environment only — no application code. The workflows check the repo out
# into /workspace and put its src/ on PYTHONPATH, so only a dependency change
# needs this rebuilt. preflight.sh enforces that by comparing /opt/uv.lock
# against the checkout's.

FROM python:3.12-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:0.9.2 /uv /uvx /bin/
WORKDIR /app

# README.md is not documentation here: pyproject declares `readme = "README.md"`.
COPY pyproject.toml uv.lock README.md ./

# Built straight at its final path — a venv's console scripts carry an absolute
# shebang, so one copied elsewhere has a /bin full of "bad interpreter".
ENV UV_PROJECT_ENVIRONMENT=/opt/venv

# uv.lock records this project as `source = { virtual = "." }`, so this installs
# the dependencies and not the project; hence PYTHONPATH below.
RUN uv sync --frozen --no-dev

FROM python:3.12-slim
WORKDIR /workspace

COPY --from=builder /opt/venv /opt/venv

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONPATH=/workspace/src \
    PYTHONUNBUFFERED=1 \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# tzdata: the pipeline resolves ZoneInfo("Asia/Jakarta") to derive the scrape
# window, and python:3.12-slim ships no zoneinfo database.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates curl git unzip tzdata fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

# `scrapling install` == `playwright install chromium` + `install-deps chromium`
# + a TLD-list refresh. Running it before Chrome means Chrome's shared library
# dependencies are already satisfied.
RUN apt-get update \
    && scrapling install \
    && rm -rf /var/lib/apt/lists/*

# The last stable 147 — same major as the Chromium snapshot the workflow pinned
# to keep scrape_bca_news.py working, which is what undetected_chromedriver
# matches on via version_main. Check that scraper before bumping it.
ARG CHROME_VERSION=147.0.7727.117
RUN CFT="https://storage.googleapis.com/chrome-for-testing-public/${CHROME_VERSION}/linux64" \
    && curl -fsSL -o /tmp/chrome.zip "${CFT}/chrome-linux64.zip" \
    && curl -fsSL -o /tmp/chromedriver.zip "${CFT}/chromedriver-linux64.zip" \
    && unzip -q /tmp/chrome.zip -d /opt \
    && unzip -q /tmp/chromedriver.zip -d /opt \
    && rm /tmp/chrome.zip /tmp/chromedriver.zip \
    # base.scraper.get_chrome_info() finds the browser by shutil.which("google-chrome").
    && ln -s /opt/chrome-linux64/chrome /usr/local/bin/google-chrome \
    && ln -s /opt/chromedriver-linux64/chromedriver /usr/local/bin/chromedriver \
    && google-chrome --version

COPY uv.lock /opt/uv.lock
