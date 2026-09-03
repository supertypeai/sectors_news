from datetime import datetime
from rapidfuzz import fuzz, process

from .models import News 
from .article_fetcher import get_article_body
from .summarizer import summarize_news
from .scorer import get_article_score
from scraper_engine.database.metadata import (
    get_sectors_data, 
    get_sectors_data_sgx, 
    build_ticker_index, 
    build_sgx_ticker_index,
    load_company_data_idx,
    load_company_data_sgx,
    load_subsector_data_idx,
    load_subsector_data_sgx,
)
from .classifier import NewsClassifier
from .company_extractor import extract_company_name 
from .utils.article_helpers import (
    clean_article,
    is_raw_ticker,
    normalize_idx_company_name,
    normalize_sgx_company_name,
)

import logging


LOGGER = logging.getLogger(__name__)


def matching_company_name(
    company_extracted: list[str],
    source_scraper: str,
    score_threshold: int = 85,
    short_query_threshold: int = 6,
) -> list[str]:
    seen = set()
    matched = []
    
    ticker_index = (
        build_sgx_ticker_index()
        if source_scraper == 'sgx'
        else build_ticker_index()
    )
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
    source_scraper: str,
    classifier: NewsClassifier
) -> dict[str, any]:
    if source_scraper == "sgx":
        companies_lookup = load_company_data_sgx()
        sectors_data = get_sectors_data_sgx()
        valid_subsectors = load_subsector_data_sgx()

    else:
        companies_lookup = load_company_data_idx()
        sectors_data = get_sectors_data()
        _, valid_subsectors = load_subsector_data_idx()

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

    sub_sector = [
        record 
        for record in sub_sector 
        if record and record != 'unknown'
    ]
    
    if not sub_sector: 
        sub_sector_llm = classifier._classify_data(
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
    
    # Directly mapping trough sectors json 
    for sub in sub_sector:
        if sub in sectors_data:
            sector = sectors_data[sub]
            break 

    return {
        "tickers": checked_tickers,
        "sub_sector": list(dict.fromkeys(sub_sector)),
        "sector": sector,
        "dimension": dimension
    }


def summarize_and_score(
    source: str, 
    timestamp: datetime, 
    source_scraper: str,
    title: str,
    prefetched_body: str,
) -> tuple[str, str, int]:
    summary = summarize_news(
        news_text=prefetched_body,
        url=source,
        title=title,
        source_scraper=source_scraper,
    )

    if not summary:
        return None

    title, body = summary

    if not title or not body:
        return None

    scoring_content = f"Title: {title}\n\nSummary: {body}"
    
    score = get_article_score(
        scoring_content, 
        timestamp,
        source_scraper,
    )

    return title, body, score


def generate_article(
    data: dict, 
    source_scraper: str, 
    min_score: int
) -> tuple[News | None, str]:
    source = data.get("source").strip()
    timestamp_str = data.get("timestamp").strip().replace("T", " ")
    timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")

    try:
        prefetched_body = data.get("article")

        if not prefetched_body:
            prefetched_body = get_article_body(source)

            if not prefetched_body:
                LOGGER.info("Skipped article with unavailable body: %s", source)
                return None, "no_retry"

            prefetched_body = clean_article(prefetched_body)

            if not prefetched_body:
                LOGGER.info("Skipped article with empty body after cleaning: %s", source)
                return None, "no_retry"

        # summarize and scoring
        summary_score_result = summarize_and_score(
            source,
            timestamp,
            source_scraper,
            title=data.get("title"),
            prefetched_body=prefetched_body,
        )

        if not summary_score_result:
            return None, 'error'

        title, body, score_result = summary_score_result
        LOGGER.info(f'Raw scoring result: {score_result}')

        if score_result < min_score: 
            LOGGER.info(f"Low score ({score_result}) for {source}. Skipping other LLM steps")
            return None, "low_score" 

        # Classify
        classifier = NewsClassifier()

        classification_results = classifier.classify_article(
            title, 
            body, 
            source_scraper
        )

        if not classification_results:
            LOGGER.error(f"Classification failed for {source}, failing article.")
            return None, "error"
        
        tags, sentiment, dimension = classification_results

        # Post-processing
        post_process_result = post_processing(
            sentiment, 
            tags, 
            body, 
            title, 
            dimension, 
            source_scraper,
            classifier
        )

        # Assemble the final News object. Incomplete data returns None
        new_article = News.try_create(
            title=title,
            body=body,
            source=source,
            timestamp=timestamp.isoformat(),
            sector=post_process_result.get("sector"),
            sub_sector=post_process_result.get("sub_sector"),
            tags=tags,
            tickers=post_process_result.get("tickers"),
            dimension=post_process_result.get("dimension"),
            score=score_result,
            thumbnail=data.get("thumbnail"),
        )

        if new_article is None:
            LOGGER.error("Invalid News data for %s. Retrying article.", source)
            return None, "error"
        
        return new_article, "ok"

    except Exception as error: 
        LOGGER.error(
            f"[ERROR] A critical, unexpected error occurred in generate_article_async for {source}: {error}",
            exc_info=True
        )
        return None, "error"

 
