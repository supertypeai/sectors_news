# Sectors News

A news scraping and classification pipeline focused on IDX (Indonesia) and SGX (Singapore) sources. The system scrapes articles, summarizes and classifies them with LLMs, scores and tags them, and posts results to Supabase.

## Features

- IDX and SGX scraping pipelines with batching
- LLM-powered summarization, tagging, and sector classification
- Article scoring and filtering before database submission
- JSON and CSV outputs
- Automated GitHub Actions workflows for scheduled runs

## Project Structure

```text
sectors_news/
├── .github/workflows/
│   ├── pipeline_idx.yaml
│   └── pipeline_sgx.yaml
├── data/
│   ├── idx/
│   └── sgx/
│   ├── outdated_news.json
│   ├── sectors_data.json
│   ├── subsectors_data.json
│   └── unique_tags.json
├── src/
│   ├── scraper_engine/
│   │   ├── base/
│   │   ├── config/
│   │   ├── database/
│   │   ├── llm/
│   │   ├── preprocessing/
│   │   ├── sources/                 # scrapers
│   │   │   ├── idx/
│   │   │   └── sgx/
│   │   ├── pipeline.py
│   │   └── server.py
│   ├── scripts/
│   │   ├── standardized_idx_filings.py
│   │   └── update_existing_tags.py
│   └── sectors_news.egg-info/
├── universal_news_scraper_main.py
├── universal_news_scraper_scraper.py
├── universal_pipeline.py
├── data.ipynb
├── pyproject.toml
├── uv.lock
└── README.md
```

## Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd sectors_news
   ```

2. **Install dependencies**
   ```bash
   uv sync
   ```

3. **Set up environment variables**

   Create a `.env` file in the root directory:

   ```env
   SUPABASE_URL=your_supabase_url
   SUPABASE_KEY=your_supabase_key

   OPENAI_API_KEY=your_openai_api_key

   GROQ_API_KEY1=your_groq_api_key
   GROQ_API_KEY2=your_groq_api_key
   GROQ_API_KEY3=your_groq_api_key
   GROQ_API_KEY4=your_groq_api_key
   GROQ_API_KEY_DEV=your_groq_api_key

   GEMINI_API_KEY=your_gemini_api_key
   GEMINI_API_KEY2=your_gemini_api_key

   PROXY=your_proxy_url
   ```

## Usage

### Register 'src' as a package

```bash
uv pip install -e .
```

### Run the IDX pipeline

```bash
uv run -m scraper_engine.pipeline main_idx --page-number 2 --batch 1
```

### Run the SGX pipeline

```bash
uv run -m scraper_engine.pipeline main_sgx --page-number 2 --batch 1
```

### Common options (IDX and SGX)

- `--page-number`
- `--filename`
- `--csv`
- `--batch`
- `--batch-size`
- `--process-only`
- `--table-name`
- `--source-scraper`

Examples:

```bash
uv run -m scraper_engine.pipeline main_idx --page-number 2 --batch 1 --batch-size 50
uv run -m scraper_engine.pipeline main_sgx --page-number 1 --batch 1 --csv
uv run -m scraper_engine.pipeline main_idx --process-only --batch 2 --batch-size 75
```

### Remove outdated news

Remove news older than 120 days and append it to `outdated_news.json`:

```bash
uv run -m scraper_engine.pipeline remove_outdated_news --table-name idx_news
uv run -m scraper_engine.pipeline remove_outdated_news --table-name sgx_news
```

## Current Sources

The scraper status indicates which news/data sources are currently functional and run with cron.

### IDX

| ID | Source                     | Status   | Reason |
|---:|----------------------------|----------|--------|
| 1  | INDONESIAN COAL AND NICKEL | Active   | - |
| 2  | GAPKI                      | Active   | - |
| 3  | MINERBA.ESDM               | Active   | - |
| 4  | ASIAN BANKING AND FINANCE  | Active   | - |
| 5  | INDONESIA MINER            | Active   | - |
| 6  | JAKARTA GLOBE              | Active   | - |
| 7  | ANTARA NEWS                | Active   | - |
| 8  | ASIAN TELECOM              | Active   | - |
| 9  | INDONESIA BUSINESS POST    | Inactive | Requires login to read the article |
| 10 | THE JAKARTA POST           | Active   | - |
| 11 | KONTAN                     | Active   | - |
| 12 | IDN FINANCIALS             | Inactive | Cannot bypass Cloudflare to get rendered HTML |
| 13 | PETROMINDO                 | Inactive | - |
| 14 | INSIGHT KONTAN             | Inactive | Needs subscription to access the article |
| 15 | FINANSIAL BISNIS           | Inactive | Failed to extract content on GitHub Actions, works locally |
| 16 | MINING.COM                 | Inactive | Source used for Sectors insider |
| 17 | EMITENNEWS.COM             | Active   | - |
| 18 | BCA NEWS                   | Active   | - |

### SGX

| ID | Source          | Status | Reason |
|---:|-----------------|--------|--------|
| 1  | BUSINESS TIMES  | Active | - |
| 2  | STRAIT TIMES    | Active | - |

## Data Outputs

- IDX outputs: `pipeline.json`, `pipeline_filtered.json`, `pipeline_yesterday.json`
- SGX outputs: `pipeline_sgx.json`, `pipeline_sgx_filtered.json`, `pipeline_sgx_yesterday.json`

### Article schema

```json
{
  "title": "Article title",
  "body": "Article content",
  "source": "Source URL",
  "timestamp": "2026-02-05 11:26:00",
  "sector": "classified_sector",
  "sub_sector": ["classified_subsector"],
  "tags": ["tag1", "tag2"],
  "tickers": ["BBCA.JK"],
  "dimension": {"...": "..."},
  "score": 82.5
}
```

## GitHub Actions

Two scheduled workflows are defined:

- `pipeline_idx.yaml`
  - Schedule: `30 4 * * *` (11:30 UTC+7, daily)
  - Runs IDX scraping, preprocessing, and submission
- `pipeline_sgx.yaml`
  - Schedule: `0 3 * * *` (10:00 UTC+7, daily)
  - Runs SGX scraping, preprocessing, and submission

Both workflows install dependencies with `uv`, set up NLTK data, run the pipeline, and commit results back to the repo.

## Maintenance Scripts

- `standardized_idx_filings.py`  
  Standardizes IDX filings data and upserts updates to Supabase.

- `update_existing_tags.py`  
  Re-tags existing records in Supabase using LLM prompts.

