from datetime import datetime
from rapidfuzz import fuzz, process

from .models import News 
from .article_fetcher import get_article_body
from .summarizer import summarize_news
from .structure_summarizer import get_structure_summary
from .scorer import get_article_score
from .classifier import classify_data
from .company_extractor import extract_company_name 
from scraper_engine.database.metadata import (
    get_sectors_data, 
    get_sectors_data_sgx, 
    load_company_data_idx,
    load_company_data_sgx,
    load_subsector_data_idx,
    load_subsector_data_sgx,
)
from scraper_engine.utils.symbol_helpers import (
    build_idx_ticker_index,
    build_sgx_ticker_index,
    is_raw_ticker,
    normalize_idx_company_name,
    normalize_sgx_company_name,
)
from scraper_engine.llm.client import TokenUsageLogger
from scraper_engine.utils.article_helpers import (
    clean_article,
)

import logging


LOGGER = logging.getLogger(__name__)


def matching_company_name(
    company_extracted: list[str],
    source_scraper: str,
    score_threshold: int = 90,
) -> list[str]:
    seen = set()
    matched = []
    
    ticker_index = (
        build_sgx_ticker_index()
        if source_scraper == 'sgx'
        else build_idx_ticker_index()
    )

    min_key_length = 5 if source_scraper == 'idx' else 2 

    normalized_funct = (
        normalize_sgx_company_name 
        if source_scraper == 'sgx' 
        else normalize_idx_company_name
    ) 

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
        company_name = company.get("company_name") 
        ticker_hint = company.get("ticker_hint")

        ticker_found = None

        if ticker_hint and is_raw_ticker(ticker_hint):
            query = ticker_hint.lower().strip()

            scorer = fuzz.ratio
            cutoff = 95
            candidates = ticker_candidates

        else:
            if not company_name: 
                continue 

            normalized = normalized_funct(company_name)
            query = normalized

            scorer = fuzz.ratio
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
            LOGGER.info(
                "input: %s -> matched: %s (score=%s) -> %s",
                query,
                matched_key,
                score,
                ticker_found,
            )
        
        else:
            LOGGER.info("input: %s -> no match above threshold", query)

        if ticker_found and ticker_found not in seen:
            seen.add(ticker_found)
            matched.append(ticker_found)

    return matched


def format_structure_body(structured_body: dict | None) -> str:
    if not structured_body:
        return ""

    sections = []

    lead = structured_body.get("lead")
    if lead:
        sections.append(lead.strip())

    for block in structured_body.get("blocks", []):
        block_type = block.get("type")
        heading = block.get("heading") or ""

        if block_type == "paragraph":
            content = block.get("text", "")

        elif block_type == "metrics":
            content = "\n".join(
                f"{metric.get('label')}: {metric.get('value')}"
                for metric in block.get("items", [])
            )

        elif block_type == "list":
            content = "\n".join(
                f"- {item}"
                for item in block.get("items", [])
            )

        else:
            continue

        content = content.strip()

        if heading:
            content = f"{heading.strip()}:\n{content}"

        if content:
            sections.append(content)

    return "\n\n".join(sections)


async def get_symbol_extracted(
    body: str, 
    title: str,
    source_scraper: str,
    token_usage_logger: TokenUsageLogger | None = None,
) -> list[str]:
    checked_tickers = []

    company_extracted = await extract_company_name(
        title=title, 
        body=body, 
        source_scraper=source_scraper,
        token_usage_logger=token_usage_logger,
    )

    if company_extracted:
        matched_tickers = matching_company_name(
            company_extracted,
            source_scraper=source_scraper
        ) 
        checked_tickers = list(matched_tickers)

    return checked_tickers


async def post_processing(
    sentiment: str, 
    tags: list[str], 
    body: str, 
    title: str,
    dimension: dict, 
    source_scraper: str,
    checked_tickers: list[str],
    token_usage_logger: TokenUsageLogger | None = None,
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
        response = await classify_data(
            body=body,
            category="subsectors",
            source_scraper=source_scraper,
            title=title,
            token_usage_logger=token_usage_logger,
        )

        sub_sector_llm = response.get("sub_sector") 

        sub_sector = [sub_sector_llm.lower()] if (
            sub_sector_llm
            and sub_sector_llm.lower() in valid_subsectors
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


async def summarize_and_score(
    source: str, 
    source_scraper: str,
    title: str,
    prefetched_body: str,
    token_usage_logger: TokenUsageLogger | None = None,
) -> tuple[str, str, dict, int] | None:
    summary = await summarize_news(
        news_text=prefetched_body,
        url=source,
        title=title,
        source_scraper=source_scraper,
        token_usage_logger=token_usage_logger,
    )

    if not summary:
        return None

    summary_title, summary_body = summary

    if not summary_title or not summary_body:
        return None

    scoring_content = f"Title: {summary_title}\n\nSummary: {summary_body}"
    
    score = await get_article_score(
        body=scoring_content, 
        source_scraper=source_scraper,
        token_usage_logger=token_usage_logger,
    )

    return summary_title, summary_body, score


async def filter_valid_articles(
    data: dict, 
    source_scraper: str, 
    min_score: int,
    token_usage_logger: TokenUsageLogger | None = None,
) -> tuple[News | None, str]:
    source = data.get("source").strip()
    timestamp_str = data.get("timestamp").strip().replace("T", " ")

    try:
        prefetched_body = data.get("article")

        if not prefetched_body:
            prefetched_body = get_article_body(source)

            if not prefetched_body:
                LOGGER.info(
                    "Skipped article with unavailable body: %s", 
                    source
                )
                return None, "no_retry"

            prefetched_body = clean_article(prefetched_body)

            if not prefetched_body:
                LOGGER.info(
                    "Skipped article with empty body after cleaning: %s", 
                    source
                )
                return None, "no_retry"

        # summarize and scoring
        # skip if score < threshold
        summary_score_result = await summarize_and_score(
            source=source,
            source_scraper=source_scraper,
            title=data.get("title"),
            prefetched_body=prefetched_body,
            token_usage_logger=token_usage_logger,
        )

        if not summary_score_result:
            return None, 'error'

        title, body, score_result = summary_score_result

        if score_result < min_score: 
            LOGGER.info(
                "Low score (%s) for %s. Skipping other LLM steps",
                score_result,
                source,
            )
            return None, "low_score" 

        output = {
            "title": title, 
            "body": body, 
            "score": score_result, 
            "article": prefetched_body,
            "timestamp": timestamp_str, 
            "source": source,
            "thumbnail": data.get("thumbnail")
        }

        return output, "ok"

    except Exception as error: 
        LOGGER.error(
            "[ERROR] A critical, unexpected error occurred in generate_article: %s",
            error,
            exc_info=True
        )
        return None, "error"


async def enrich_articles(
    article_uniques: dict,
    source_scraper: str,
    top_200_symbols_sgx: set[str] | None,
    token_usage_logger: TokenUsageLogger | None = None,
) -> tuple[News | None, str]:
    title = article_uniques["title"]
    prefetched_body = article_uniques["article"]
    source = article_uniques["source"]
    timestamp = article_uniques["timestamp"]
    body = article_uniques["body"]
    score_result = article_uniques["score"]
    thumbnail = article_uniques["thumbnail"]

    structured_body = await get_structure_summary(
        title=title,
        article=prefetched_body,
        source=source,
        timestamp=timestamp,
        token_usage_logger=token_usage_logger,
    )

    structured_body_str = format_structure_body(
        structured_body=structured_body,
    )

    symbols_extracted = await get_symbol_extracted(
        body=structured_body_str,
        title=title,
        source_scraper=source_scraper,
        token_usage_logger=token_usage_logger,
    )

    if source_scraper == "sgx":
        if top_200_symbols_sgx is None:
            LOGGER.error(
                "Cannot process SGX article without the top-200 symbol set: %s",
                source,
            )
            return None, "error"

        if symbols_extracted:
            has_top_200_symbol = any(
                symbol in top_200_symbols_sgx
                for symbol in symbols_extracted
            )

            if not has_top_200_symbol:
                LOGGER.info(
                    "Skipping SGX article; no symbol is in the top 200.",
                )
                return None, "not_top_200"

    classification_results = await classify_data(
        title=title,
        body=structured_body_str,
        category="classification",
        source_scraper=source_scraper,
        token_usage_logger=token_usage_logger,
    )

    if not classification_results:
        LOGGER.error(
            "Classification failed for %s, failing article.",
            source,
        )
        return None, "error"

    tags = classification_results.get("tags")
    sentiment = classification_results.get("sentiment")
    dimension = classification_results.get("dimension")

    post_process_result = await post_processing(
        sentiment,
        tags,
        structured_body_str,
        title,
        dimension,
        source_scraper,
        symbols_extracted,
        token_usage_logger,
    )

    new_article = News.try_create(
        title=title,
        body=body,
        source=source,
        timestamp=timestamp,
        sector=post_process_result.get("sector"),
        sub_sector=post_process_result.get("sub_sector"),
        tags=tags,
        tickers=symbols_extracted,
        structured_body=structured_body,
        dimension=post_process_result.get("dimension"),
        score=score_result,
        thumbnail=thumbnail,
    )

    if new_article is None:
        LOGGER.error(
            "Invalid News data for %s. Retrying article.",
            source,
        )
        return None, "error"

    return new_article, "ok"
 
