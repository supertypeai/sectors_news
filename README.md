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

| ID | Source                                                                      | Status   | Reason |
|---:|-----------------------------------------------------------------------------|----------|--------|
| 1  | [Indonesian Coal and Nickel](https://www.indonesiancoalandnickel.com)       | Active   | - |
| 2  | [GAPKI (Palm Oil Association)](https://gapki.id)                            | Active   | - |
| 3  | [Minerba ESDM (Mining Ministry)](https://www.minerba.esdm.go.id)            | Active   | - |
| 4  | [Asian Banking and Finance](https://asianbankingandfinance.net)              | Active   | - |
| 5  | [Indonesia Miner](https://indonesiaminer.com)                               | Active   | - |
| 6  | [Jakarta Globe](https://jakartaglobe.id)                                    | Active   | - |
| 7  | [Antara News](https://www.antaranews.com)                                   | Active   | - |
| 8  | [Asian Telecom](https://asiantelecom.com)                                   | Active   | - |
| 9  | [The Jakarta Post](https://www.thejakartapost.com)                          | Active   | - |
| 10 | [Kontan Investasi](https://www.kontan.co.id/search/indeks?kanal=investasi)  | Active   | - |
| 11 | [Kontan Keuangan](https://www.kontan.co.id/search/indeks?kanal=keuangan)    | Active   | - |
| 12 | [IDN Financials](https://www.idnfinancials.com)                             | Active   | - |
| 13 | [Bisnis.com](https://www.bisnis.com)                                        | Active   | - |
| 14 | [Bloomberg Technoz](https://www.bloombergtechnoz.com)                       | Active   | - |
| 15 | [Investor.id](https://investor.id)                                          | Active   | - |
| 16 | [Emiten News](https://emitennews.com)                                       | Active   | - |
| 17 | [BCA Sekuritas News](https://bcasekuritas.co.id)                            | Active   | - |
| 18 | [CNBC Indonesia Market](https://www.cnbcindonesia.com/market)               | Active   | - |
| 19 | [CNN Indonesia Ekonomi](https://www.cnnindonesia.com/ekonomi)               | Active   | - |
| 20 | [Kompas Money](https://indeks.kompas.com/?site=money)                       | Active   | - |
| 21 | [Finance Detik](https://finance.detik.com/bursa-dan-valas)                  | Active   | - |
| 22 | [Indonesia Business Post](https://indonesiabusinesspost.com)                | Inactive | Requires login to read the article |
| 23 | [Petromindo](https://www.petromindo.com)                                    | Inactive | - |
| 24 | [Insight Kontan](https://insight.kontan.co.id)                              | Inactive | Needs subscription to access the article |
| 25 | [Mining.com](https://www.mining.com)                                        | Inactive | Source used for Sectors insider |

### SGX

| ID | Source                                                                      | Status | Reason |
|---:|-----------------------------------------------------------------------------|--------|--------|
| 1  | [Business Times](https://www.businesstimes.com.sg)                          | Active | - |
| 2  | [The Straits Times](https://www.straitstimes.com)                           | Active | - |
| 3  | [Channel NewsAsia (CNA)](https://www.channelnewsasia.com)                   | Active | - |
| 4  | [Singapore Business Review (SBR)](https://sbr.com.sg)                      | Active | - |

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

Both workflows install dependencies with `uv`, run the pipeline, and commit results back to the repo.

## Maintenance Scripts

- `standardized_idx_filings.py`  
  Standardizes IDX filings data and upserts updates to Supabase.

- `update_existing_tags.py`  
  Re-tags existing records in Supabase using LLM prompts.

