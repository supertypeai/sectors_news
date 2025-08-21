"""
Script to submit 
"""

from preprocessing_articles.run_prepros_article import generate_article

from config.setup import LOGGER, SUPABASE_KEY, SUPABASE_URL

import pandas as pd 
import time
import requests
import json
import argparse
import time 


MININUM_SCORE = 60
BATCH_SIZE = 5


def post_articles(jsonfile):
  with open(f'./data/{jsonfile}.json', 'r') as f:
    articles = json.load(f)

  headers = {
    'Authorization': f'Bearer {SUPABASE_KEY}',
    'Content-Type': 'application/json'
  }

  response = requests.post(SUPABASE_URL + '/articles/list', json=articles, headers=headers)

  if response.status_code == 200:
    print('Success:', response.json())
  else:
    print('Failed:', response.status_code, response.text)


def post_article(jsonfile):
  with open(f'./data/{jsonfile}.json', 'r') as f:
    article = json.load(f)

  if isinstance(article, list):
    article = article[0]
  
  headers = {
    'Authorization': f'Bearer {SUPABASE_KEY}',
    'Content-Type': 'application/json'
  }

  response = requests.post(SUPABASE_URL + '/articles', json=article, headers=headers)

  if response.status_code == 200:
    print('Success:', response.json())
  else:
    print('Failed:', response.status_code, response.text)


def send_data_to_db(successful_articles: list):
  """ 
  Sends the processed articles to the database in batches.
  This function takes a list of successfully processed articles and submits them to the database in batches.
    
  Args:
      successful_articles (list): A list of dictionaries containing the processed articles to be submitted.
  """
  # Supabase submission with batch
  for i in range(0, len(successful_articles), BATCH_SIZE):
    batch_to_submit = successful_articles[i:i + BATCH_SIZE]
    LOGGER.info(f"Submitting batch {i//BATCH_SIZE + 1} with {len(batch_to_submit)} articles...")

    batch_headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }
    response = requests.post(f"{SUPABASE_URL}/rest/v1/idx_news", json=batch_to_submit, headers=batch_headers)
    
    if 200 <= response.status_code < 300:
        LOGGER.info(f'  Batch Submission Success: {response.status_code}')
    else:
        LOGGER.info(f'  Batch Submission Failed: {response.status_code} - {response.text}')
  return response


def get_article_to_process(jsonfile: str, batch: int, batch_size: int,) -> list[str]:
  """ 
  Retrieves articles from a JSON file and filters out those that already exist in the database.

  Args:
      jsonfile (str): The name of the JSON file containing articles to be processed.
    
  Returns:
      list[str]: A list of articles that are not already present in the database.
  """
  try: 
    # Open the JSON file and load the articles
    with open(f'./data/{jsonfile}.json', 'r') as f:
      all_articles = json.load(f)
    
    # Headers for Supabase database connection
    db_headers = {"apikey": SUPABASE_KEY,
                  "Authorization": f"Bearer {SUPABASE_KEY}"
                  }
    # Check if the database is reachable and get existing articles
    all_articles_db = requests.get(f"{SUPABASE_URL}/rest/v1/idx_news?select=*",
                                    headers=db_headers
                                  ).json()
    
    # Create a set of existing links from the database
    existing_links = {db_article.get('source') for db_article in all_articles_db}
      
    # Filter out articles that already exist in the database
    articles_to_process = [article for article in all_articles if article.get('source') not in existing_links]
    
    # Calculate total needed batches
    total_articles = len(articles_to_process)
    max_needed_batches = (total_articles + batch_size - 1) // batch_size
    
    # If current batch is beyond what's needed, return empty
    if batch > max_needed_batches:
        LOGGER.info(f"Batch {batch} not needed. Only {max_needed_batches} batches required for {total_articles} articles")
        return []

    # Split to batch
    start_idx = (batch - 1) * batch_size
    end_idx = min(start_idx + batch_size, total_articles) 

    LOGGER.info(f"Total Article to process: {len(articles_to_process)}")  
    LOGGER.info(f"Batch {batch}/{max_needed_batches}: Processing articles {start_idx} to {end_idx-1}")

    return articles_to_process[start_idx:end_idx]
  
  except (FileNotFoundError, requests.RequestException, KeyError) as error:
      LOGGER.error(f"Failed during setup phase: {error}")
      return []


def post_source(jsonfile: str,
                batch: int, batch_size: int, 
                is_check_csv: bool = False):
  """
  Posts articles to the database server after processing them.
  This function reads articles from a JSON file, processes each article to generate 
  a News object, and submits them to the database in batches.
  If an article fails to process, it is added to a retry queue for a second attempt.

  Args:
      jsonfile (str): The name of the JSON file containing articles to be processed.
      is_check_csv (bool): Flag to indicate whether to save the final processed articles to a CSV file for verification.
  """
  # Initialize lists to hold successful articles and failed articles for retry
  successful_articles = []
  failed_articles_queue = []
  start_time = time.time()

  data_articles = get_article_to_process(jsonfile, batch, batch_size) 
  if not data_articles:
    LOGGER.info(f"Batch {batch}: No articles to process. Exiting early.")
    return 
  
  LOGGER.info(f"Batch {batch}: Processing {len(data_articles)} articles")

  for article_data in data_articles:
    source_url = article_data.get('source')
    LOGGER.info(f'Processing: {source_url}')
    
    try:
      # Get all the necessary data with LLM calls
      processed_article_object = generate_article(article_data)

      # Check for the failure signal from the processing function
      if not processed_article_object:
          raise ValueError("generate_article returned None, signaling a failure.")

      processed_article = processed_article_object.to_dict()

      # Check the score and decide whether to batch it
      if processed_article.get('score', 0) > MININUM_SCORE:
          LOGGER.info(f"  [SUCCESS] Article will be batched. Score: {processed_article.get('score')}")
          successful_articles.append(processed_article)
      else:
          LOGGER.info(f"  [SKIPPED] Low score: {processed_article.get('score')}")

    except Exception as error:
      LOGGER.error(f"  [FAILED] Adding to retry queue. Reason: {error}")
      failed_articles_queue.append(article_data)
      continue
  
  if failed_articles_queue:
    for article_data in failed_articles_queue:
      source_url = article_data.get('source')
      LOGGER.info(f' [RETRY] Retrying for URL: {source_url}')

      try:
        processed_article_object = generate_article(article_data)
        # Check for the failure signal from the processing function
        if not processed_article_object:
            raise ValueError("generate_article returned None, signaling a failure.")

        processed_article = processed_article_object.to_dict()

        if processed_article.get('score', 0) > MININUM_SCORE:
            LOGGER.info(f"  [SUCCESS] Article will be batched. Score: {processed_article.get('score')}")
            successful_articles.append(processed_article)
        else:
            LOGGER.info(f"  [SKIPPED] Low score: {processed_article.get('score')}")

      except Exception as error:
        LOGGER.error(f"  [FAILED ON RETRY] Giving up on {source_url}: {error}")

  # Final Batch 
  end_time = time.time()
  LOGGER.info(f"Total processing time: {end_time - start_time:.2f} seconds")

  if successful_articles:
    LOGGER.info(f"\n--- PREPARING TO SUBMIT {len(successful_articles)} ARTICLES IN BATCHES OF {BATCH_SIZE} ---")
    
    # Saving to CSV to verify the output 
    if is_check_csv:
      df = pd.DataFrame(successful_articles)
      df.to_csv("final_processed_articles.csv", index=False)
      LOGGER.info("All successful articles saved to final_processed_articles.csv")

    # Push data with batch processing
    response = send_data_to_db(successful_articles)

    if 200 <= response.status_code < 300:
        LOGGER.info(f"  Batch Submission Success: {response.status_code}")
        LOGGER.info(f"  Batch {batch}: COMPLETED SUCCESSFULLY - Processed {len(data_articles)} articles")
    else:
        LOGGER.info(f"  Batch Submission Failed: {response.status_code} - {response.text}")
        LOGGER.error(f"  Batch {batch}: FAILED during database submission")
  else:
      LOGGER.info("\nNo articles met the criteria for submission.")
      LOGGER.info(f"Batch {batch}: COMPLETED - Processed {len(data_articles)} articles, but none met submission criteria")


def main():
  parser = argparse.ArgumentParser(description="Script for posting articles to database server")
  parser.add_argument("filename", type=str, default="labeled_articles")
  parser.add_argument("--list", action='store_true', help="Flag to indicate posting a list of articles")
  parser.add_argument("--i", action='store_true', help="Flag to use LLM inferencing")

  args = parser.parse_args()

  filename = args.filename
  
  if args.i:
    post_source(filename)
  elif args.list:
    post_articles(filename)
  else:
    post_article(filename)


if __name__ == "__main__":
  main()

# Sample usage
# python ./scripts/server.py filename --list