from scraper_engine.preprocessing.run_prepros_article import generate_article_async
from scraper_engine.config.conf import SUPABASE_KEY, SUPABASE_URL
from scraper_engine.database.client import SUPABASE_CLIENT

import pandas as pd 
import time
import requests
import json
import time 
import os 
import shutil
import traceback 
import time 
import asyncio
import logging


LOGGER = logging.getLogger(__name__)

MININUM_SCORE = 60
BATCH_SIZE = 5


def send_data_to_db(successful_articles: list, table_name: str):
  """
  Insert processed articles into the specified database table.

  Args:
    successful_articles (list): List of processed article records to insert.
    table_name (str): Target database table name.
  """
  # Supabase submission with batch
  for index in range(0, len(successful_articles), BATCH_SIZE):
    batch_to_submit = successful_articles[index:index + BATCH_SIZE]
    LOGGER.info(f"Submitting batch {index//BATCH_SIZE + 1} with {len(batch_to_submit)} articles...")

    batch_headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }
    response = requests.post(f"{SUPABASE_URL}/rest/v1/{table_name}", json=batch_to_submit, headers=batch_headers)
    
    if 200 <= response.status_code < 300:
        LOGGER.info(f' Batch Submission Success: {response.status_code}')
    else:
        LOGGER.info(f' Batch Submission Failed: {response.status_code} - {response.text}')
  return response


def filter_article_to_process(
  all_articles_db: list[dict], 
  all_articles: list[dict[str]], 
  all_articles_yesterday: list[str]
) -> list[dict[str]]:
  """
    Filters articles to process by removing duplicates, articles already in the database, 
    and articles that were processed yesterday.

    Args:
      all_articles_db (list[dict]): A list of dictionary of articles already in the database.
      all_articles (list[dict]): A list of all articles to be processed.
      all_articles_yesterday (list[str]): A list of article sources processed yesterday.

    Returns:
        list[dict]: A list of filtered articles ready for processing.
    """
  try:
    # Create a set of existing links from the database
    existing_links = {db_article.get('source') for db_article in all_articles_db}
      
    # Filter out articles that already exist in the database
    articles_to_process = [article for article in all_articles if article.get('source') not in existing_links]

    # Filter out duplicate source
    seen_sources = set()
    filter_duplicate_articles = []

    for article in articles_to_process:
      source = article.get('source')
      if source not in seen_sources:
        seen_sources.add(source)
        filter_duplicate_articles.append(article)
    
    # Filter out same sources with pipeline yesterday
    final_articles_to_process = []

    for article in filter_duplicate_articles:
      source = article.get('source')
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
  source_scraper: str
) -> list[dict[str]]:
  """ 
  Retrieves articles from a JSON file and filters out those that already exist in the database.

  Args:
    jsonfile (str): The name of the JSON file containing articles to be processed.
    batch (int): The batch index (1-based) indicating which chunk of articles to process. 
    batch_size (int): Number of articles to include in each batch.
    table_name (str): Database table used for existence checks.
    source_scraper (str): Scraper/source identifier for filtering.

  Returns:
      list[dict[str]]: A list of articles that are not already present in the database.
  """
  filtered_file = f'./data/{source_scraper}/{jsonfile}_filtered.json'
  yesterday_file = f'./data/{source_scraper}/{jsonfile}_yesterday.json'

  try:
    if batch == 1: 
      LOGGER.info("Batch 1: Performing fresh filtering against database")
            
      # Open the JSON file and load the articles
      with open(f'./data/{jsonfile}.json', 'r') as file_pipeline:
        all_articles = json.load(file_pipeline)
      
      # Open pipeline json yesterday 
      all_articles_yesterday = []
      if os.path.exists(yesterday_file):
        try:
          with open(yesterday_file, 'r') as file_pipeline_yesterday:
            data = json.load(file_pipeline_yesterday)

            if isinstance(data, list):
              all_articles_yesterday = [
                item.get('source') if isinstance(item, dict) else item 
                for item in data
              ]
            else:
              all_articles_yesterday = []

        except Exception as error:
              LOGGER.warning(f"Failed to read yesterday file: {error}. Starting fresh")
              all_articles_yesterday = []

      # Check if the database is reachable and get existing articles
      try:
        response = (
          SUPABASE_CLIENT
          .table(table_name)
          .select('source')
          .execute()
        )
        all_articles_db = response.data
      except Exception as error: 
        LOGGER.error(f"Database Error: {error}")
        all_articles_db = []

      # Filter articles
      LOGGER.info(f'Total article scraped {len(all_articles)}')
      final_articles_to_process = filter_article_to_process(all_articles_db, all_articles, all_articles_yesterday)

      # Update yesterday pipeline checkpoint with raw pipeline.json
      shutil.copy(f"./data/{jsonfile}.json", yesterday_file)

      # Save the filtered list for subsequent batches
      with open(filtered_file, 'w') as file:
          json.dump(final_articles_to_process, file, indent=2)

      LOGGER.info(f"Saved filtered article list to {filtered_file} for subsequent batches")
      
    else: 
      LOGGER.info(f"Batch {batch}: Using pre-filtered article list from batch 1")
            
      if os.path.exists(filtered_file):
          with open(filtered_file, 'r') as file:
            final_articles_to_process = json.load(file)
          LOGGER.info(f"Loaded {len(final_articles_to_process)} articles from filtered list")
      else:
          LOGGER.error(f"Filtered article file not found: {filtered_file}")
          LOGGER.error("Make sure batch 1 has completed successfully before running this batch")
          return []

    # Calculate total needed batches
    total_articles = len(final_articles_to_process)
    max_needed_batches = (total_articles + batch_size - 1) // batch_size
    
    # If current batch is beyond what's needed, return empty
    if batch > max_needed_batches:
        LOGGER.info(f"Batch {batch} not needed. Only {max_needed_batches} batches required for {total_articles} articles")
        return []

    # Split to batch
    start_idx = (batch - 1) * batch_size
    end_idx = min(start_idx + batch_size, total_articles) 

    LOGGER.info(f"Total Article to process: {len(final_articles_to_process)}")  
    LOGGER.info(f"Batch {batch}/{max_needed_batches}: Processing articles {start_idx} to {end_idx-1}")

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
    is_check_csv: bool = False
):
  """
  Load articles from a JSON file, process a selected batch, and post them
  to the database.

  Args:
    jsonfile (str): Path to the JSON file containing articles.
    batch (int): 1-based batch index to process.
    batch_size (int): Number of articles per batch.
    table_name (str): Target database table.
    source_scraper (str): Source identifier for the articles.
    is_sgx (bool): Apply SGX-specific processing logic if True.
    is_check_csv (bool): Save processed articles to CSV for verification.
  """
  # Initialize lists to hold successful articles and failed articles for retry
  successful_articles = []
  failed_articles_queue = []
  start_time = time.time()

  data_articles = get_article_to_process(jsonfile, batch, batch_size, table_name, source_scraper)

  if not data_articles:
    LOGGER.info(f"Batch {batch}: No articles to process. Exiting early.")
    return 
  
  LOGGER.info(f"Batch {batch}: Processing {len(data_articles)} articles")

  for article_data in data_articles:
    source_url = article_data.get('source')
    LOGGER.info(f'Processing: {source_url}')
    
    try:
      # Get all the necessary data with LLM calls
      processed_article_object = await generate_article_async(article_data, source_scraper, is_sgx)
      await asyncio.sleep(5)
      
      # Check for the failure signal from the processing function
      if not processed_article_object:
          raise ValueError("generate_article returned None, signaling a failure.")

      processed_article = processed_article_object.to_dict()

      # Check the score and decide whether to batch it
      if processed_article.get('score', 0) > MININUM_SCORE:
          LOGGER.info(f" [SUCCESS] Article will be batched. Score: {processed_article.get('score')}")
          successful_articles.append(processed_article)
      else:
          LOGGER.info(f" [SKIPPED] Low score: {processed_article.get('score')}")

    except Exception as error:
      LOGGER.error(f" [FAILED] Adding to retry queue. Reason: {error}")
      failed_articles_queue.append(article_data)
      continue
  
  if failed_articles_queue:
    for article_data in failed_articles_queue:
      source_url = article_data.get('source')
      LOGGER.info(f' [RETRY] Retrying for URL: {source_url}')

      try:
        processed_article_object = await generate_article_async(article_data, source_scraper, is_sgx)
        
        # Check for the failure signal from the processing function
        if not processed_article_object:
            raise ValueError("generate_article returned None, signaling a failure.")

        processed_article = processed_article_object.to_dict()

        if processed_article.get('score', 0) > MININUM_SCORE:
            LOGGER.info(f" [SUCCESS] Article will be batched. Score: {processed_article.get('score')}")
            successful_articles.append(processed_article)
        else:
            LOGGER.info(f" [SKIPPED] Low score: {processed_article.get('score')}")

      except Exception as error:
        LOGGER.error(f" [FAILED ON RETRY] Giving up on {source_url}: {error}")

  # Final Batch 
  end_time = time.time()
  LOGGER.info(f"Total processing time: {end_time - start_time:.2f} seconds")

  if successful_articles:
    LOGGER.info(f"\n--- PREPARING TO SUBMIT {len(successful_articles)} ARTICLES IN BATCHES OF {BATCH_SIZE} ---")
    
    # Saving to CSV to verify the output 
    if is_check_csv:
      df = pd.DataFrame(successful_articles)
      df.to_csv("final_processed_articles_{table_name}.csv", index=False)
      LOGGER.info("All successful articles saved to final_processed_articles.csv")

    # Push data with batch processing
    response = send_data_to_db(successful_articles, table_name)

    if 200 <= response.status_code < 300:
        LOGGER.info(f" Batch Submission Success: {response.status_code}")
        LOGGER.info(f" Batch {batch}: COMPLETED SUCCESSFULLY - Processed {len(data_articles)} articles")
    else:
        LOGGER.info(f" Batch Submission Failed: {response.status_code} - {response.text}")
        LOGGER.error(f" Batch {batch}: FAILED during database submission")
  else:
      LOGGER.info("\nNo articles met the criteria for submission.")
      LOGGER.info(f"Batch {batch}: COMPLETED - Processed {len(data_articles)} articles, but none met submission criteria")

