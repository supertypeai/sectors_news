from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from rapidfuzz import fuzz, process

from .models import News 
from .summarizer import summarize_news, get_article_body
from .scorer import get_article_score
from scraper_engine.database.metadata import get_sectors_data, get_sectors_data_sgx, build_ticker_index, build_sgx_ticker_index
from .classifier import (
    load_company_data, NewsClassifier, 
    load_sub_sectors_data, load_company_data_sgx, load_sub_sectors_data_sgx
)
from .company_extractor import extract_company_name 

import re
import logging


LOGGER = logging.getLogger(__name__)


CLASSIFIER = NewsClassifier()
EXECUTOR = ThreadPoolExecutor(max_workers=4)
COMPANY_DATA_IDX = load_company_data()
COMPANY_DATA_SGX = load_company_data_sgx()
SUBSECTOR_DATA = load_sub_sectors_data()
SUBSECTOR_DATA_SGX = load_sub_sectors_data_sgx()
TICKER_INDEX = build_ticker_index()
TICKER_INDEX_SGX = build_sgx_ticker_index()
SECTORS_DATA = get_sectors_data()
SECTORS_DATA_SGX = get_sectors_data_sgx()


def is_raw_ticker(text: str) -> bool:
    cleaned = text.strip()
    return bool(re.match(r'^[A-Z]{2,6}$', cleaned))


def normalize_idx_company_name(raw: str) -> str:
    name = re.sub(r'^\s*PT\s+', '', raw, flags=re.IGNORECASE)
    name = re.sub(r'\s*Tbk\.?$', '', name, flags=re.IGNORECASE)
    name = re.sub(r'\s*\(Persero\)\s*', ' ', name, flags=re.IGNORECASE)
    return re.sub(r'\s+', ' ', name).strip().lower()


def normalize_sgx_company_name(raw: str) -> str:
    name = re.sub(r'\s*Ltd\.?$', '', raw, flags=re.IGNORECASE)
    name = re.sub(r'\s*Limited\.?$', '', name, flags=re.IGNORECASE)
    name = re.sub(r'\s*Pte\.?$', '', name, flags=re.IGNORECASE)
    name = re.sub(r'\s*Bhd\.?$', '', name, flags=re.IGNORECASE)
    return re.sub(r'\s+', ' ', name).strip().lower()


def matching_company_name(
    company_extracted: list[str],
    source_scraper: str,
    score_threshold: int = 85,
    short_query_threshold: int = 6,
) -> list[str]:
    seen = set()
    matched = []
    
    ticker_index = TICKER_INDEX_SGX if source_scraper == 'sgx' else TICKER_INDEX
    min_key_length = 5 if source_scraper == 'idx' else 2 
    normalized_funct = normalize_sgx_company_name if source_scraper == 'sgx' else normalize_idx_company_name

    name_candidates = {
        key: value
        for key, value in ticker_index.items()
        if len(key) >= min_key_length
    }

    ticker_candidates = {
        value.lower().replace('.jk', '').strip(): value
        for value in ticker_index.values()
    }

    for company in company_extracted:
        ticker_found = None

        if is_raw_ticker(company):
            query = company.lower().strip()
            scorer = fuzz.ratio
            cutoff = 95
            candidates = ticker_candidates
        else:
            normalized = normalized_funct(company)
            query = normalized

            if len(normalized) < short_query_threshold:
                scorer = fuzz.ratio
                cutoff = 90
            else:
                scorer = fuzz.token_set_ratio
                cutoff = score_threshold

            candidates = name_candidates

        result = process.extractOne(
            query,
            candidates.keys(),
            scorer=scorer,
            score_cutoff=cutoff,
        )

        if result:
            matched_key, score, _ = result
            ticker_found = candidates[matched_key]
            LOGGER.info(f"input: {query!r} -> matched: {matched_key!r} (score={score}) -> {ticker_found}")
        else:
            LOGGER.info(f"input: {query!r} -> no match above threshold")

        if ticker_found and ticker_found not in seen:
            seen.add(ticker_found)
            matched.append(ticker_found)

    return matched


def post_processing(
    sentiment: str, 
    tags: list[str], 
    body: str, 
    title: str,
    dimension: dict, 
    source_scraper: str
) -> dict[str, any]:
    companies_lookup = COMPANY_DATA_SGX if source_scraper == "sgx" else COMPANY_DATA_IDX
    sectors_data = SECTORS_DATA_SGX if source_scraper == "sgx" else SECTORS_DATA
    valid_subsectors = SUBSECTOR_DATA_SGX if source_scraper == "sgx" else SUBSECTOR_DATA

    # Sentiment added to tag
    if sentiment != 'Not Applicable':
        tags.append(sentiment)
        
    # Get tickers 
    checked_tickers = []

    if source_scraper == 'sgx':
        company_extracted = extract_company_name(body, source_scraper)
        LOGGER.info(f'raw company: {company_extracted}')

        if company_extracted:
            matched_tickers = matching_company_name(company_extracted, source_scraper='sgx') 
            checked_tickers = list(matched_tickers)

    else: 
        company_extracted = extract_company_name(body, source_scraper) or []
        LOGGER.info(f'raw company: {company_extracted}')

        if company_extracted: 
            matched_tickers = matching_company_name(company_extracted, source_scraper='idx')
            checked_tickers = list(matched_tickers)

    # Sub sector
    sub_sector = []

    if checked_tickers: 
        sub_sector = [
            companies_lookup[ticker]["sub_sector"]
            for ticker in checked_tickers
            if ticker in companies_lookup
        ]

    if not sub_sector: 
        sub_sector_llm = CLASSIFIER._classify_data(
            body=body,
            category="subsectors",
            source_scraper=source_scraper,
            title=title,
        )

        sub_sector = [sub_sector_llm[0].lower()] if (
            sub_sector_llm
            and sub_sector_llm[0].lower() in valid_subsectors
        ) else []

    # Sectors data 
    sector = None 
    
    if checked_tickers:
        for ticker in checked_tickers:
            company = companies_lookup.get(ticker, {})
            sector_extracted = company.get("sector")
            if sector_extracted:
                sector = sector_extracted
                break

    if not sector:
        for sub in sub_sector:
            if sub in sectors_data:
                sector = sectors_data[sub]
                break 

    return {
        "tickers": checked_tickers,
        "sub_sector": sub_sector,
        "sector": sector,
        "dimension": dimension
    }


def summarize_and_score(source: str, timestamp: datetime, source_scraper: str) -> tuple[str, str, int]:
    article = get_article_body(source)
    if not article:
        return None

    summary = summarize_news(news_text=article, url=source)
    if not summary:
        return None

    title, body = summary
    if not title or not body:
        return None

    score = get_article_score(body, timestamp, source, source_scraper)
    return title, body, score


def generate_article(data: dict, source_scraper: str, min_score: int) -> tuple[News | None, str]:
    source = data.get("source").strip()
    timestamp_str = data.get("timestamp").strip().replace("T", " ")
    timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")

    try:
        # summarize and scoring 
        summary_score_result = summarize_and_score(source, timestamp, source_scraper)

        if not summary_score_result:
            return None, 'error'

        title, body, score_result = summary_score_result

        if score_result < min_score: 
            LOGGER.info(f"Low score ({score_result}) for {source}. Skipping other LLM steps")
            return None, "low_score" 

        # Classify
        classification_results = CLASSIFIER.classify_article(title, body, source_scraper)

        if not classification_results:
            LOGGER.error(f"Classification failed for {source}, failing article.")
            return None, 'error'
        
        tags, sentiment, dimension = classification_results

        # Assemble the final News object
        new_article = News(
            title=title, 
            body=body, 
            source=source,
            timestamp=timestamp.isoformat(),
            score=score_result,
            tags=tags, 
            tickers=[], 
            sub_sector=[], 
            sector="",
            dimension=None
        )

        # Post-processing
        post_process_result = post_processing(
            sentiment, 
            tags, 
            body, 
            title, 
            dimension, 
            source_scraper
        )
        new_article.tickers = post_process_result.get("tickers")
        new_article.sub_sector = post_process_result.get("sub_sector")
        new_article.sector = post_process_result.get("sector")
        new_article.dimension = post_process_result.get("dimension")
        
        return new_article, 'ok'

    except Exception as error: 
        LOGGER.error(
            f"[ERROR] A critical, unexpected error occurred in generate_article_async for {source}: {error}",
            exc_info=True
        )
        return None, 'error'

 