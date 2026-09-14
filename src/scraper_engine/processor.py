from scraper_engine.preprocessing.article_builder import generate_article
from scraper_engine.database.client import SUPABASE_CLIENT
from scraper_engine.base.scraper import SeleniumScraper
from scraper_engine.llm.client import TokenUsageLogger
from scraper_engine.utils.json_helpers import read_json, write_json
from scraper_engine.utils.symbol_helpers import (
    add_sgx_suffix,
    get_top_200_symbols,
)

from datetime import datetime, timezone, timedelta
from json import JSONDecodeError
from pathlib import Path

import pandas as pd
import time
import shutil
import traceback
import logging


LOGGER = logging.getLogger(__name__)

WIB = timezone(timedelta(hours=7))

MININUM_SCORE = 65


def send_data_to_db(successful_articles: list, table_name: str):
    LOGGER.info("Submitting %d articles", len(successful_articles))
    
    try:
        response = (
            SUPABASE_CLIENT
            .table(table_name)
            .insert(successful_articles)
            .execute()
        )
        
        LOGGER.info(
            "Submission Success. Inserted %d rows.",
            len(response.data),
        )
    
    except Exception as error:
        LOGGER.error("Submission Failed: %s", error)


def filter_articles_by_time(
    articles: list[dict],
    filter_from: datetime,
) -> list[dict]:
    """
    Keeps only articles whose timestamp is >= filter_from (WIB).
    Articles with unparseable timestamps are kept (fail-open).
    """
    filtered = []

    for article in articles:
        source_url = article.get("source", "")

        # SGX Market Updates expose a publication date but no time of day
        if (
            "research-education/market-updates/" in source_url
            or "smallcapasia.com/" in source_url
        ):
            filtered.append(article)
            continue

        timestamp = article.get("timestamp")

        if not timestamp:
            filtered.append(article)
            continue

        try:
            dt = datetime.fromisoformat(timestamp)
            dt = dt.replace(tzinfo=WIB) if dt.tzinfo is None else dt.astimezone(WIB)

            if dt >= filter_from:
                filtered.append(article)

        except (ValueError, TypeError):
            filtered.append(article)

    return filtered


def get_existing_sources(
    table_name: str,
    filter_from: datetime | None = None,
) -> set:
    """
    Return the set of article `source` URLs already present in the table.
    Used both when building the work-list and as a per-batch resume check.
    """
    try:
        query = (
            SUPABASE_CLIENT
            .table(table_name)
            .select("source")
        )

        if filter_from:
            start_of_day = filter_from.replace(hour=0, minute=0, second=0, microsecond=0)
            query = query.gte("created_at", start_of_day.isoformat())

        return {
            row.get("source") 
            for row in query.execute().data
        }

    except Exception as error:
        LOGGER.error("Database Error: %s", error)
        return set()


def filter_article_to_process(
    existing_links: set,
    all_articles: list[dict[str]],
    all_articles_yesterday: list[str],
) -> list[dict[str]]:
    """
    Filters articles to process by removing duplicates, database entries,
    and yesterday’s processed articles.
    """
    try:
        articles_to_process = [
            article
            for article in all_articles
            if article.get("source") not in existing_links
        ]

        seen_sources = set()
        filter_duplicate_articles = []

        for article in articles_to_process:
            source = article.get("source")

            if source not in seen_sources:
                seen_sources.add(source)
                filter_duplicate_articles.append(article)

        final_articles_to_process = [
            article
            for article in filter_duplicate_articles
            if article.get('source') not in all_articles_yesterday
        ]

        LOGGER.info(
            "Final articles to process: %d",
            len(final_articles_to_process),
        )
        return final_articles_to_process

    except Exception as error:
        LOGGER.error("Error in filtering articles: %s", error)
        LOGGER.error("Traceback: %s", traceback.format_exc())
        return []


def build_filtered_article(
    jsonfile: str,
    table_name: str,
    source_scraper: str,
    filter_from: datetime | None = None,
): 
    data_directory = Path("data") / source_scraper
    source_file = data_directory / f"{jsonfile}.json"
    filtered_file = data_directory / f"{jsonfile}_filtered.json"
    yesterday_file = data_directory / f"{jsonfile}_yesterday.json"

    LOGGER.info("Performing filtering against database")

    all_articles = read_json(source_file)

    LOGGER.info("Total raw article scraped: %d", len(all_articles))
    
    all_articles = filter_articles_by_time(all_articles, filter_from)
    
    LOGGER.info("Total articles in time window: %d", len(all_articles))

    all_articles_yesterday = []

    if yesterday_file.exists():
        try:
            data = read_json(yesterday_file)

            if isinstance(data, list):
                all_articles_yesterday = [
                    item.get("source")
                    if isinstance(item, dict)
                    else item
                    for item in data
                ]

        except Exception as error:
            LOGGER.warning(
                "Failed to read yesterday file: %s. Starting fresh",
                error,
            )

    existing_links = get_existing_sources(table_name, filter_from)

    LOGGER.info("Total article scraped %d", len(all_articles))

    final_articles_to_process = filter_article_to_process(
        existing_links,
        all_articles,
        all_articles_yesterday,
    )

    shutil.copy(source_file, yesterday_file)
    write_json(filtered_file, final_articles_to_process)

    LOGGER.info("Saved filtered article list to %s", filtered_file)


def get_article_to_process(
    jsonfile: str,
    batch: int,
    batch_size: int,
    table_name: str,
    source_scraper: str,
    filter_from: datetime | None = None,
) -> list[dict[str]]:
    """
    Retrieves articles from JSON and filters out those already in the database.
    """
    filtered_file = (
        Path("data")
        / source_scraper
        / f"{jsonfile}_filtered.json"
    )

    if not filtered_file.exists():
        LOGGER.error("Filtered article file not found: %s", filtered_file)
        return []

    try:
        final_articles_to_process = read_json(filtered_file)

    except (JSONDecodeError, OSError) as error:
        LOGGER.error(
            "Failed to read filtered file %s: %s",
            filtered_file,
            error,
        )
        return []

    LOGGER.info(
        "Loaded %d articles from work-list",
        len(final_articles_to_process),
    )

    total_articles = len(final_articles_to_process)
    max_needed_batches = (total_articles + batch_size - 1) // batch_size

    if batch > max_needed_batches:
        LOGGER.info(
            "Batch %d not needed. Only %d batches required",
            batch,
            max_needed_batches,
        )
        return []

    start_idx = (batch - 1) * batch_size
    end_idx = min(start_idx + batch_size, total_articles)
    batch_slice = final_articles_to_process[start_idx:end_idx]

    LOGGER.info(
        "Batch %d/%d: articles %d to %d",
        batch,
        max_needed_batches,
        start_idx,
        end_idx - 1,
    )

    # resume-safety: the DB is the checkpoint. Skip any article already
    # inserted, so a re-run (after a crashed batch) processes only what's left.
    existing_sources = get_existing_sources(table_name, filter_from)
    
    remaining = [
        article
        for article in batch_slice
        if article.get("source") not in existing_sources
    ]

    skipped = len(batch_slice) - len(remaining)

    if skipped:
        LOGGER.info(
            "Batch %d: skipping %d already-processed article(s)",
            batch,
            skipped,
        )

    return remaining


def process_article(
    article_data: dict,
    source_scraper: str,
    top_200_symbols_sgx: set[str],
    token_usage_logger: TokenUsageLogger,
) -> tuple[dict | None, str]:
    try:
        article_object, status = generate_article(
            data=article_data,
            source_scraper=source_scraper,
            min_score=MININUM_SCORE,
            top_200_symbols_sgx=top_200_symbols_sgx,
            token_usage_logger=token_usage_logger,
        )

        time.sleep(1)

        # skipped 
        if status in {"low_score", "no_retry", "not_top_200"}:
            return None, status

        # get into queue failed retry
        if status != "ok" or not article_object:
            return None, "error"

        return article_object.to_dict(), "ok"

    except Exception as error:
        LOGGER.error("Article processing failed: %s", error)
        return None, "error"


def log_total_llm_cost(token_usage_logger: TokenUsageLogger) -> None:
    total_cost = sum(
        cost
        for cost in token_usage_logger.request_costs
        if cost is not None
    )

    LOGGER.info(
        "Total reported cost: $%.8f USD | completed requests: %d | missing cost: %d",
        total_cost,
        len(token_usage_logger.request_costs),
        token_usage_logger.request_costs.count(None),
    )


def post_source(
    jsonfile: str,
    batch: int,
    batch_size: int,
    table_name: str,
    source_scraper: str,
    filter_from: datetime | None = None,
    is_check_csv: bool = False,
):
    """
    Load articles, process selected batch, and post to database.
    """
    successful_articles = []
    failed_articles_queue = []

    start_time = time.time()
    token_usage_logger = TokenUsageLogger()

    data_articles = get_article_to_process(
        jsonfile,
        batch,
        batch_size,
        table_name,
        source_scraper,
        filter_from,
    )

    if not data_articles:
        LOGGER.info("Batch %d: No articles to process.", batch)
        log_total_llm_cost(token_usage_logger)
        return

    LOGGER.info(
        "Batch %d: Processing %d articles",
        batch,
        len(data_articles),
    )
    
    try: 
        # only need this when processing sgx news 
        top_200_symbols_sgx = set()
        if source_scraper == "sgx":
            top_200_symbols_sgx = get_top_200_symbols()

        for index, article_data in enumerate(
            data_articles, 
            start=1
        ):
            source_url = article_data.get("source")

            LOGGER.info(
                "Processing %d/%d | source: %s", 
                index, 
                len(data_articles), 
                source_url 
            )

            processed_article, status = process_article(
                article_data=article_data,
                source_scraper=source_scraper,
                top_200_symbols_sgx=top_200_symbols_sgx,
                token_usage_logger=token_usage_logger,
            )

            if status == "error":
                failed_articles_queue.append(article_data)

            elif processed_article:
                successful_articles.append(processed_article)

            time.sleep(1)

        # process the failed in queue lists 
        for index, article_data in enumerate(
            failed_articles_queue, 
            start=1
        ):
            source_url = article_data.get("source")

            LOGGER.info(
                "Processing Failed Retry %d/%d | source: %s", 
                index, 
                len(failed_articles_queue), 
                source_url  
            )

            processed_article, status = process_article(
                article_data=article_data,
                source_scraper=source_scraper,
                top_200_symbols_sgx=top_200_symbols_sgx,
                token_usage_logger=token_usage_logger,
            )

            if processed_article:
                successful_articles.append(processed_article)

            time.sleep(1)

    finally:
        LOGGER.info("All processing done. Closing Shared WebDriver.")
        SeleniumScraper.close_shared_driver()

    end_time = time.time()
    final_time = (end_time - start_time) / 60
    
    LOGGER.info(
        "Total processing time: %d minute", 
        final_time
    )

    log_total_llm_cost(token_usage_logger)

    run_sending_data(
        batch=batch, 
        successful_articles=successful_articles, 
        source_scraper=source_scraper, 
        table_name=table_name, 
        is_check_csv=is_check_csv
    )


def run_sending_data(
    batch: int,
    successful_articles: list, 
    source_scraper: str,
    table_name: str,  
    is_check_csv: bool
):
    if successful_articles:
        # temp: add symbols duplicate tickers 
        if source_scraper == 'idx':
            for record in successful_articles: 
                tickers_value = record.get('tickers')
                record['symbols'] = tickers_value.copy()
        
        else: 
            for record in successful_articles:
                record['symbols'] = record.pop('tickers', None)

            # sgx symbols are stored with the .SI suffix
            for record in successful_articles:
                record['symbols'] = add_sgx_suffix(record.get('symbols'))

        if is_check_csv:
            df = pd.DataFrame(successful_articles)
            df.to_csv(
                f"final_processed_articles_{table_name}.csv",
                index=False,
            )

        send_data_to_db(
            successful_articles,
            table_name,
        )

    else:
        LOGGER.info(
            "Batch %d: Completed, no articles met criteria",
            batch,
        )
