# Sectors News

A comprehensive news scraping and classification system that automatically collects financial and business news from multiple sources, classifies them by sectors and subsectors, and stores them in a database. The system includes both universal news scrapers and specialized sector-specific scrapers.

## 🚀 Features

- **Multi-source News Scraping**: Scrapes news from 10+ financial and business news sources
- **Sector Classification**: Automatically classifies news articles into 9 main sectors and 30+ subsectors
- **Universal Scraper**: Handles major international news sources (Bloomberg, CNBC, Reuters, etc.)
- **Specialized Scrapers**: Sector-specific scrapers for Indonesian markets (mining, oil & gas, etc.)
- **Automated Pipeline**: GitHub Actions for scheduled scraping and database updates
- **Machine Learning**: Multiple classification approaches (BERT, Logistic Regression, Keyword-based)
- **Data Export**: Supports JSON and CSV output formats

## 📁 Project Structure

```
sectors_news/
├── base_model/                 # Base scraper classes and utilities
│   ├── scraper.py             # Base Scraper class
│   └── scraper_collection.py  # ScraperCollection for managing multiple scrapers
├── models/                    # Individual scraper implementations
│   ├── scrape_idnfinancials.py
│   ├── scrape_petromindo.py
│   ├── scrape_icn.py
│   ├── scrape_gapki.py
│   ├── scrape_minerba.py
│   ├── scrape_abaf.py
│   ├── scrape_kontan.py
│   ├── scrape_idnminer.py
│   ├── scrape_jakartaglobe.py
│   ├── scrape_idx.py
│   └── scrape_mining.py
├── scripts/                   # Pipeline and server scripts
│   ├── pipeline.py           # Main scraping pipeline
│   └── server.py             # Database submission utilities
├── data/                     # Data files and outputs
│   ├── subsectors.json       # Sector and subsector definitions
│   ├── subsectors_data.json
│   ├── mining.json
│   ├── pipeline.json
│   └── abaf.txt
├── universal_news_scraper_main.py    # Universal scraper entry point
├── universal_news_scraper_scraper.py # Universal scraper implementations
├── universal_pipeline.py             # Universal scraper pipeline
├── data.ipynb                       # Data analysis notebook
└── requirements.txt                  # Python dependencies
```

## 🛠️ Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd sectors_news
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables**
   Create a `.env` file in the root directory with the following variables:
   ```env
   DATABASE_URL=your_database_url
   DB_KEY=your_database_key
   OPENAI_API_KEY=your_openai_api_key
   SUPABASE_URL=your_supabase_url
   SUPABASE_KEY=your_supabase_key
   PROXY=your_proxy_url  # Optional
   ```

## 🚀 Usage

### 1. Universal News Scraper

Scrape from major international news sources:

```bash
# Scrape all sources (0-9)
python universal_news_scraper_main.py all

# Scrape specific source by index
python universal_news_scraper_main.py 3  # IDX only

# Scrape range of sources
python universal_news_scraper_main.py 0:7  # Sources 0-6
```

**Available Sources:**
- 0: IDN_FINANCIALS
- 1: CNBC
- 2: YAHOO_FINANCE
- 3: IDX
- 4: CNN_EDITION
- 5: FINANCE_DETIK
- 6: EKONOMI_BISNIS
- 7: MARKET_WATCH (requires proxy)
- 8: REUTERS (requires proxy)
- 9: BLOOMBERG (requires proxy)

### 2. Sector-Specific Pipeline

Run the main scraping pipeline with sector-specific scrapers:

```bash
# Basic usage
python scripts/pipeline.py 2 pipeline

# With CSV output
python scripts/pipeline.py 2 pipeline --csv

# Custom page count and filename
python scripts/pipeline.py 5 my_articles --csv
```

### 3. Database Submission

Submit scraped articles to the database:

```bash
# Submit single article
python scripts/server.py filename

# Submit list of articles
python scripts/server.py filename --list

# Submit with LLM inference
python scripts/server.py filename --i
```

### 4. Universal Pipeline

Submit data from files to the database:

```bash
python universal_pipeline.py filename1 filename2
```

## 📊 Data Structure

### Sectors and Subsectors

The system classifies news into 9 main sectors:

1. **Infrastructures**: telecommunication, heavy-constructions, utilities, transportation-infrastructure
2. **Energy**: oil-gas-coal, alternative-energy
3. **Financials**: financing-service, investment-service, insurance, banks, holding-investment-companies
4. **Consumer Cyclicals**: apparel-luxury-goods, consumer-services, automobiles-components, media-entertainment, household-goods, leisure-goods, retailing
5. **Technology**: software-it-services, technology-hardware-equipment
6. **Industrials**: industrial-services, multi-sector-holdings, industrial-goods
7. **Healthcare**: healthcare-equipment-providers, pharmaceuticals-health-care-research
8. **Basic Materials**: basic-materials
9. **Properties & Real Estate**: properties-real-estate
10. **Transportation & Logistics**: logistics-deliveries, transportation
11. **Consumer Non-Cyclicals**: tobacco, nondurable-household-products, food-staples-retailing, food-beverage

### Article Data Structure

```json
{
  "title": "Article title",
  "body": "Article content",
  "source": "Source URL",
  "date": "Publication date",
  "sector": "classified_sector",
  "subsector": "classified_subsector",
  "score": 85.5
}
```

## 🔄 GitHub Actions

The project includes two automated workflows:

### 1. Daily Pipeline (`pipeline.yaml`)
- **Schedule**: Runs daily at 10:00 AM UTC+7 (3:00 AM UTC)
- **Trigger**: Manual dispatch also available
- **Actions**:
  - Sets up Python 3.10 environment
  - Installs dependencies
  - Runs scraping pipeline for all news sources
  - Submits results to database
  - Commits and pushes changes

### 2. Periodic Scraping (`actions.yaml`)
- **Schedule**: Runs every 3rd day of the month at 10:00 AM UTC+7
- **Trigger**: Manual dispatch also available
- **Actions**:
  - Scrapes from IDN Financials
  - Scrapes from IDX (100 pages)
  - Runs universal scraper for sources 0-6
  - Commits and pushes results

## 🔧 Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `DATABASE_URL` | Database API endpoint | Yes |
| `DB_KEY` | Database authentication key | Yes |
| `OPENAI_API_KEY` | OpenAI API key for LLM inference | Yes |
| `SUPABASE_URL` | Supabase project URL | Yes |
| `SUPABASE_KEY` | Supabase API key | Yes |
| `proxy` | Proxy URL for restricted sources | No |

### Dependencies

Key dependencies include:
- `beautifulsoup4`: Web scraping
- `requests_html`: Advanced web requests
- `transformers`: BERT and transformer models
- `torch`: PyTorch for ML models
- `scikit_learn`: Traditional ML algorithms
- `pandas`: Data manipulation
- `python-dotenv`: Environment variable management

## 📈 Data Analysis

The `data.ipynb` notebook provides examples of:
- Loading and analyzing scraped data
- Sector distribution analysis
- Text preprocessing for ML models
- Model training and evaluation

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request
