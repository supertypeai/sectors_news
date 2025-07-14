"""
Script to submit 
"""
from preprocessing_articles.run_prepros_article import generate_article

import time
import requests
from dotenv import load_dotenv
import os
import json
import argparse
import openai
import time 
import pandas as pd 
from config.setup import LOGGER, SUPABASE_KEY, SUPABASE_URL

load_dotenv(override=True)

MININUM_SCORE = 10

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


def post_source(jsonfile):
    with open(f'./data/{jsonfile}.json', 'r') as f:
        articles = json.load(f)
    
    articles = articles[:7]
    print(f"Total articles scraped on pipeline.json: {len(articles)}")

    # headers = {
    #     'Authorization': f'Bearer {SUPABASE_KEY}',
    #     'Content-Type': 'application/json'
    # }
    
    # Get all existing articles from the database
    if isinstance(articles, list):
      all_articles_db = requests.get(f"{SUPABASE_URL}/rest/v1/idx_news?select=*",
                                      headers={
                                          "apiSUPABASE_KEY": SUPABASE_KEY,
                                          "Authorization": f"Bearer {SUPABASE_KEY}"
                                        }
                                    ).json()
     
      links = [article_db['source'] for article_db in all_articles_db]
      
      final_submit_batch = []  # To hold articles for batch submission
      BATCH_SIZE = 5  # Modify this to your desired batch size
      
      start = time.time()
      for article in articles:
          if article.get('source') not in links:
              print(f"\nProcessing Source: {article.get('source')}")
              
              # processed_article = None 
              # for attempt in range(3):
              #   try:
              #     processed_article_object = generate_article(article)
            
              #     # processed_article = processed_article_object.model_dump_json()
              #     processed_article = processed_article_object.to_dict()
              #     break 
              #   except openai.RateLimitError:
              #     wait_time = (attempt + 1) * 10 # Wait longer each time
              #     print(f"Rate limit hit. Waiting for {wait_time} seconds before retrying...\n")
              #     time.sleep(wait_time)
              try:
                  processed_article_object = generate_article(article)
                  processed_article = processed_article_object.to_dict()
              except Exception as error:
                  LOGGER.error(f"Failed to process article {article.get('source')}: {error}")
                  return None

              links.append(article['source'])

              # Check if the article's score meets the minimum threshold
              if processed_article.get('score') is not None and processed_article.get('score') > MININUM_SCORE:
                final_submit_batch.append(processed_article)
                print(f"Article added to batch: {processed_article['source']}")

                # Check if batch size reached
                if len(final_submit_batch) >= BATCH_SIZE:
                    print(f"TEST batch of {BATCH_SIZE} articles...")
                    df = pd.DataFrame(final_submit_batch)
                    df.to_csv("test_batch_flow.csv", mode='a', header=False, index=False)
                    # batch_response =  requests.post(
                    #                                 f"{SUPABASE_URL}/rest/v1/idx_news",
                    #                                 json=final_submit_batch,  
                    #                                 headers={
                    #                                         "apiSUPABASE_KEY": SUPABASE_KEY,
                    #                                         "Authorization": f"Bearer {SUPABASE_KEY}",
                    #                                         "Content-Type": "application/json",
                    #                                         "Prefer": "return=representation"  # optional for returning rows
                    #                                     }
                    #                             )
                    # if batch_response.status_code == 200:
                    #     print('Batch Submission Success:', batch_response.json())
                    # else:
                    #     print('Batch Submission Failed:', batch_response.status_code, batch_response.text)
                    
                    # Reset batch list
                    final_submit_batch = []
              else:
                  print(f"Article skipped due to low score: {processed_article.get('source')} (Score: {processed_article.get('score')})")
          else:
              print("Article already exists")
        
        # Submit remaining articles in the batch if any
      if final_submit_batch:
          end_time = time.time()
          print(f"Writing remaining batch of {len(final_submit_batch)} articles to CSV…")

          df = pd.DataFrame(final_submit_batch)
          df.to_csv("test_all_flow.csv", index=False)
          LOGGER.info(f"END TIME: {end_time - start}")
            # print(f"Submitting remaining batch of {len(final_submit_batch)} articles...")
            # batch_response = requests.post(
            #                       f"{SUPABASE_URL}/rest/v1/idx_news",
            #                       json=final_submit_batch,
            #                       headers={
            #                           "apiSUPABASE_KEY": SUPABASE_KEY,
            #                           "Authorization": f"Bearer {SUPABASE_KEY}",
            #                           "Content-Type": "application/json",
            #                           "Prefer": "return=representation"
            #                       }
            #                   )
            # if batch_response.status_code == 200:
            #     print('Final Batch Submission Success:', batch_response.json())
            # else:
            #     print('Final Batch Submission Failed:', batch_response.status_code, batch_response.text)


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