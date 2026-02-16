from scraper_engine.preprocessing.run_prepros_article import generate_article_async
from scraper_engine.database.client import SUPABASE_CLIENT
from scraper_engine.base.scraper import SeleniumScraper

import pandas as pd
import time
import requests
import json
import os
import shutil
import traceback
import asyncio
import logging


LOGGER = logging.getLogger(__name__)

MININUM_SCORE = 60
BATCH_SIZE = 5


def send_data_to_db(successful_articles: list, table_name: str):
    """
    Insert processed articles into the specified database table.
    """
    for index in range(0, len(successful_articles), BATCH_SIZE):
        batch_to_submit = successful_articles[index:index + BATCH_SIZE]

        LOGGER.info(
            f"Submitting batch {index // BATCH_SIZE + 1} "
            f"with {len(batch_to_submit)} articles..."
        )

        try:
            response = (
                SUPABASE_CLIENT
                .table(table_name)
                .insert(batch_to_submit)
                .execute()
            )

            LOGGER.info(f"Batch Submission Success. Inserted {len(response.data)} rows.")
        
        except Exception as error:
            error_message = str(error)
            LOGGER.error(f"Batch Submission Failed: {error_message}")


def filter_article_to_process(
    all_articles_db: list[dict],
    all_articles: list[dict[str]],
    all_articles_yesterday: list[str],
) -> list[dict[str]]:
    """
    Filters articles to process by removing duplicates, database entries,
    and yesterday’s processed articles.
    """
    try:
        existing_links = {
            db_article.get("source") for db_article in all_articles_db
        }

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

        final_articles_to_process = []

        for article in filter_duplicate_articles:
            source = article.get("source")
            if source in all_articles_yesterday:
                continue
            final_articles_to_process.append(article)

        return final_articles_to_process

    except Exception as error:
        LOGGER.error(f"Error in filtering articles: {error}")
        LOGGER.error(f"Traceback: {traceback.format_exc()}")
        return []


def get_article_to_process(
    jsonfile: str,
    batch: int,
    batch_size: int,
    table_name: str,
    source_scraper: str,
) -> list[dict[str]]:
    """
    Retrieves articles from JSON and filters out those already in the database.
    """
    filtered_file = f"./data/{source_scraper}/{jsonfile}_filtered.json"
    yesterday_file = f"./data/{source_scraper}/{jsonfile}_yesterday.json"

    try:
        if batch == 1:
            LOGGER.info("Batch 1: Performing fresh filtering against database")

            with open(f"./data/{source_scraper}/{jsonfile}.json", "r") as file_pipeline:
                all_articles = json.load(file_pipeline)

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

            try:
                response = (
                    SUPABASE_CLIENT
                    .table(table_name)
                    .select("source")
                    .execute()
                )
                all_articles_db = response.data

            except Exception as error:
                LOGGER.error(f"Database Error: {error}")
                all_articles_db = []

            LOGGER.info(f"Total article scraped {len(all_articles)}")

            final_articles_to_process = filter_article_to_process(
                all_articles_db,
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

        else:
            LOGGER.info(
                f"Batch {batch}: Using pre-filtered article list from batch 1"
            )

            if os.path.exists(filtered_file):
                with open(filtered_file, "r") as file:
                    final_articles_to_process = json.load(file)
                LOGGER.info(
                    f"Loaded {len(final_articles_to_process)} articles"
                )
            else:
                LOGGER.error(f"Filtered article file not found: {filtered_file}")
                return []

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

        LOGGER.info(
            f"Batch {batch}/{max_needed_batches}: "
            f"Processing articles {start_idx} to {end_idx - 1}"
        )

        return final_articles_to_process[start_idx:end_idx]

    except (FileNotFoundError, requests.RequestException, KeyError) as error:
        LOGGER.error(f"Failed during setup phase: {error}")
        return []


async def post_source(
    jsonfile: str,
    batch: int,
    batch_size: int,
    table_name: str,
    source_scraper: str,
    is_sgx: bool = False,
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
                processed_article_object = await generate_article_async(
                    article_data,
                    source_scraper,
                    is_sgx,
                )

                await asyncio.sleep(5)

                if not processed_article_object:
                    raise ValueError("generate_article returned None.")

                processed_article = processed_article_object.to_dict()

                if processed_article.get("score", 0) > MININUM_SCORE:
                    successful_articles.append(processed_article)
                else:
                    LOGGER.info(
                        f"Skipped due to low score: "
                        f"{processed_article.get('score')}"
                    )

            except Exception as error:
                LOGGER.error(f"Failed. Adding to retry queue. Reason: {error}")
                failed_articles_queue.append(article_data)

        for article_data in failed_articles_queue:
            source_url = article_data.get("source")
            LOGGER.info(f"Retrying for URL: {source_url}")

            try:
                processed_article_object = await generate_article_async(
                    article_data,
                    source_scraper,
                    is_sgx,
                )

                await asyncio.sleep(5)

                if not processed_article_object:
                    raise ValueError("generate_article returned None.")

                processed_article = processed_article_object.to_dict()

                if processed_article.get("score", 0) > MININUM_SCORE:
                    successful_articles.append(processed_article)

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

    if successful_articles:
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
