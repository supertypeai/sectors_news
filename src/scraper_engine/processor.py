from scraper_engine.preprocessing.article_builder import generate_article
from scraper_engine.database.client import SUPABASE_CLIENT
from scraper_engine.base.scraper import SeleniumScraper

from datetime import datetime, timezone, timedelta

import pandas as pd
import time
import json
import os
import shutil
import traceback
import logging


LOGGER = logging.getLogger(__name__)

WIB = timezone(timedelta(hours=7))

MININUM_SCORE = 65
SGX_SYMBOL_SUFFIX = ".SI"


def send_data_to_db(successful_articles: list, table_name: str):
    LOGGER.info(f"Submitting {len(successful_articles)} articles")
    
    try:
        response = (
            SUPABASE_CLIENT
            .table(table_name)
            .insert(successful_articles)
            .execute()
        )
        
        LOGGER.info(f"Submission Success. Inserted {len(response.data)} rows.")
    
    except Exception as error:
        LOGGER.error(f"Submission Failed: {error}")


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
        LOGGER.error(f"Database Error: {error}")
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

        LOGGER.info(f'Final articles to process: {len(final_articles_to_process)}')
        return final_articles_to_process

    except Exception as error:
        LOGGER.error(f"Error in filtering articles: {error}")
        LOGGER.error(f"Traceback: {traceback.format_exc()}")
        return []


def build_filtered_article(
    jsonfile: str,
    table_name: str,
    source_scraper: str,
    filter_from: datetime | None = None,
): 
    filtered_file = f"./data/{source_scraper}/{jsonfile}_filtered.json"
    yesterday_file = f"./data/{source_scraper}/{jsonfile}_yesterday.json"

    LOGGER.info("Performing filtering against database")

    with open(f"./data/{source_scraper}/{jsonfile}.json", "r") as file_pipeline:
        all_articles = json.load(file_pipeline)

    LOGGER.info(f"Total raw article scraped: {len(all_articles)}")
    
    all_articles = filter_articles_by_time(all_articles, filter_from)
    
    LOGGER.info(f"Total articles in time window: {len(all_articles)}")

    all_articles_yesterday = []

    if os.path.exists(yesterday_file):
        try:
            with open(yesterday_file, "r") as file_pipeline_yesterday:
                data = json.load(file_pipeline_yesterday)

                if isinstance(data, list):
                    all_articles_yesterday = [
                        item.get("source")
                        if isinstance(item, dict)
                        else item
                        for item in data
                    ]

        except Exception as error:
            LOGGER.warning(
                f"Failed to read yesterday file: {error}. Starting fresh"
            )

    existing_links = get_existing_sources(table_name, filter_from)

    LOGGER.info(f"Total article scraped {len(all_articles)}")

    final_articles_to_process = filter_article_to_process(
        existing_links,
        all_articles,
        all_articles_yesterday,
    )

    shutil.copy(
        f"./data/{source_scraper}/{jsonfile}.json",
        yesterday_file,
    )

    with open(filtered_file, "w") as file:
        json.dump(final_articles_to_process, file, indent=2)

    LOGGER.info(
        f"Saved filtered article list to {filtered_file}"
    ) 


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
    filtered_file = f"./data/{source_scraper}/{jsonfile}_filtered.json"

    if not os.path.exists(filtered_file):
        LOGGER.error(f"Filtered article file not found: {filtered_file}")
        return []

    try:
        with open(filtered_file, "r") as file:
            final_articles_to_process = json.load(file)

    except (json.JSONDecodeError, OSError) as error:
        LOGGER.error(f"Failed to read filtered file {filtered_file}: {error}")
        return []

    LOGGER.info(f"Loaded {len(final_articles_to_process)} articles from work-list")

    total_articles = len(final_articles_to_process)
    max_needed_batches = (total_articles + batch_size - 1) // batch_size

    if batch > max_needed_batches:
        LOGGER.info(
            f"Batch {batch} not needed. "
            f"Only {max_needed_batches} batches required"
        )
        return []

    start_idx = (batch - 1) * batch_size
    end_idx = min(start_idx + batch_size, total_articles)
    batch_slice = final_articles_to_process[start_idx:end_idx]

    LOGGER.info(
        f"Batch {batch}/{max_needed_batches}: "
        f"articles {start_idx} to {end_idx - 1}"
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
            f"Batch {batch}: skipping {skipped} already-processed article(s)"
        )

    return remaining


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

    data_articles = get_article_to_process(
        jsonfile,
        batch,
        batch_size,
        table_name,
        source_scraper,
        filter_from,
    )

    if not data_articles:
        LOGGER.info(f"Batch {batch}: No articles to process.")
        return

    LOGGER.info(
        f"Batch {batch}: Processing {len(data_articles)} articles"
    )
    
    try: 
        for article_data in data_articles:
            source_url = article_data.get("source")
            LOGGER.info(f"Processing: {source_url}")

            try:
                processed_article_object, status = generate_article(
                    article_data,
                    source_scraper,
                    MININUM_SCORE
                )

                if status == "low_score":
                    LOGGER.info(f"Skipped due to low score: {source_url}")
                    continue

                if status == "no_retry":
                    LOGGER.info(f"Skipped because article body is unavailable: {source_url}")
                    continue
                
                time.sleep(5)

                if status != "ok" or not processed_article_object:
                    LOGGER.error("Failed. Adding to retry queue.")
                    failed_articles_queue.append(article_data)
                    continue

                processed_article = processed_article_object.to_dict()
                LOGGER.info(f"succes article above threshold: {source_url}")
                successful_articles.append(processed_article)

            except Exception as error:
                LOGGER.error(f"Failed. Adding to retry queue. Reason: {error}")
                failed_articles_queue.append(article_data)

        for article_data in failed_articles_queue:
            source_url = article_data.get("source")
            LOGGER.info(f"Retrying for URL: {source_url}")

            try:
                processed_article_object, status = generate_article(
                    article_data,
                    source_scraper,
                    MININUM_SCORE
                )

                time.sleep(5)

                if status == "low_score":
                    LOGGER.info(f"Retry skipped due to low score: {source_url}")
                    continue

                if status == "no_retry":
                    LOGGER.info(f"Retry skipped because article body is unavailable: {source_url}")
                    continue

                if status != "ok" or not processed_article_object:
                    LOGGER.error(f"Failed on retry. Giving up on {source_url}")
                    continue

                LOGGER.info(f"succes article retry above threshold: {source_url}")
                successful_articles.append(processed_article_object.to_dict())

            except Exception as error:
                LOGGER.error(
                    f"Failed on retry. Giving up on {source_url}: {error}"
                )
    
    finally:
        LOGGER.info("All processing done. Closing Shared WebDriver.")
        SeleniumScraper.close_shared_driver()

    end_time = time.time()
    final_time = (end_time - start_time) / 60
    
    LOGGER.info(
        f"Total processing time: {final_time} seconds"
    )

    run_sending_data(
        batch=batch, 
        successful_articles=successful_articles, 
        source_scraper=source_scraper, 
        table_name=table_name, 
        is_check_csv=is_check_csv
    )


def filter_top_200(articles: list):
    response = (
        SUPABASE_CLIENT
        .table('sgx_company_report')
        .select('symbol, market_cap')
        .order('market_cap', desc=True)
        .limit(200)
        .execute()
    )

    response_reit = (
        SUPABASE_CLIENT
        .table('sgx_reit_profile')
        .select('symbol')
        .execute()
    )

    record_db = response.data + response_reit.data 

    symbols_db = {
        record['symbol'] 
        for record in record_db
    }

    final_articles = []

    for record in articles: 
        symbols = record.get('symbols') or []

        if not symbols:
            # keep general/untagged news
            final_articles.append(record)   
            continue

        contain_top_200 = False 

        for symbol in symbols: 
            if symbol in symbols_db: 
                contain_top_200 = True 
                break 

        if not contain_top_200: 
            LOGGER.info(
                f'Skipping article, all symbols not in top 200: {record['source']}'
            )
            continue 
        
        final_articles.append(record)

    return final_articles


def add_sgx_suffix(symbols: list[str] | None) -> list[str]:
    if not symbols:
        return symbols if symbols is not None else []

    return [
        symbol if symbol.upper().endswith(SGX_SYMBOL_SUFFIX) else f"{symbol}{SGX_SYMBOL_SUFFIX}"
        for symbol in symbols
    ]


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

            # flow to filter out if article
            # contains all symbols outside top 200 by mcap
            successful_articles = filter_top_200(successful_articles)

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
            f"Batch {batch}: Completed, no articles met criteria"
        )
