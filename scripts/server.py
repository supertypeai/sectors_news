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
import pandas as pd 

load_dotenv(override=True)

URL = os.environ.get('SUPABASE_URL')
print(URL)
KEY = os.environ.get('SUPABASE_KEY')
MININUM_SCORE = 10

def post_articles(jsonfile):
  with open(f'./data/{jsonfile}.json', 'r') as f:
    articles = json.load(f)

  headers = {
    'Authorization': f'Bearer {KEY}',
    'Content-Type': 'application/json'
  }

  response = requests.post(URL + '/articles/list', json=articles, headers=headers)

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
    'Authorization': f'Bearer {KEY}',
    'Content-Type': 'application/json'
  }

  response = requests.post(URL + '/articles', json=article, headers=headers)

  if response.status_code == 200:
    print('Success:', response.json())
  else:
    print('Failed:', response.status_code, response.text)

# def post_source(jsonfile):
#   with open(f'./data/{jsonfile}.json', 'r') as f:
#     articles = json.load(f)
#   headers = {
#     'Authorization': f'Bearer {KEY}',
#     'Content-Type': 'application/json'
#   }
  
  
#   if isinstance(articles, list):
#     # Discard redundant entries
#     all_articles_db = requests.get(URL + '/articles', headers=headers).json()
#     links = []
#     for article_db in all_articles_db:
#       if article_db['source'] not in links:
#         links.append(article_db['source'])
#     # print(links)
    
#     # Classify article metadata
#     submit_article = []
#     for article in articles:
#       if article['source'] not in links:
#         response = requests.post(URL + '/url-article', json=article, headers=headers)
    

#         if response.status_code == 200:
#           print('Inference Success:', response.json()['source'])
#           submit_article.append(response.json())
#           links.append(article['source'])
#         else:
#           print('Inference Failed:', response.status_code, response.text)
#     # print(submit_article)
#       else:
#         print("Article already exists")
    
#     submit_index = []
#     for i, article in enumerate(submit_article):
#       print(article)
#       # response = requests.post(URL + '/evaluate-article', json=article, headers=headers)
#       # print("score:", response.json()['score'])
      
#       # if int(response.json()['score']) > MININUM_SCORE:
#         # submit_index.append(i)
        
#       if article['score'] > MININUM_SCORE:
#         submit_index.append(i)
    
#     print(submit_index)
    
#     final_submit = []
#     for i in submit_index:
#       final_submit.append(submit_article[i])
    
#     # with open('./submit.json', 'w') as f:
#       # f.write(json.dumps(submit_article))
#     with open('./final.json', 'w') as f:
#       f.write(json.dumps(final_submit))
#     response = requests.post(URL + '/articles/list', json=final_submit, headers=headers)
#     if response.status_code == 200:
#       print('Success:', response.json())
#       submit_article.append(response.json())
#     else:
#       print('Failed:', response.status_code, response.text)
        
def post_source(jsonfile):
    with open(f'./data/{jsonfile}.json', 'r') as f:
        articles = json.load(f)
    
    articles = articles[:2]
    print(f"Total articles scraped on pipeline.json: {len(articles)}")

    headers = {
        'Authorization': f'Bearer {KEY}',
        'Content-Type': 'application/json'
    }
    
    # Get all existing articles from the database
    if isinstance(articles, list):
      all_articles_db = requests.get(URL + '/articles', headers=headers).json()
        
      links = [article_db['source'] for article_db in all_articles_db]
      print(links, '\n')
      
      final_submit_batch = []  # To hold articles for batch submission
      BATCH_SIZE = 5  # Modify this to your desired batch size
      
      for article in articles:
          if article['source'] not in links:
              print("Processing Each Source \n")
            
              processed_article = None 
              for attempt in range(3):
                try:
                  processed_article_object = generate_article(article)
            
                  # processed_article = processed_article_object.model_dump_json()
                  processed_article = processed_article_object.to_dict()
                  break 
                except openai.RateLimitError:
                  wait_time = (attempt + 1) * 10 # Wait longer each time
                  print(f"Rate limit hit. Waiting for {wait_time} seconds before retrying...\n")
                  time.sleep(wait_time)

                links.append(article['source'])

              # Check if the article's score meets the minimum threshold
              if processed_article['score'] is not None and processed_article['score'] > MININUM_SCORE:
                final_submit_batch.append(processed_article)
                print(f"Article added to batch: {processed_article['source']}")

                # Check if batch size reached
                if len(final_submit_batch) >= BATCH_SIZE:
                    print(f"TEST batch of {BATCH_SIZE} articles...")
                    # batch_response =  requests.post(
                    #                                 f"{URL}/rest/v1/idx_news",
                    #                                 json=final_submit_batch,  
                    #                                 headers={
                    #                                         "apikey": KEY,
                    #                                         "Authorization": f"Bearer {KEY}",
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
          print(f"Writing remaining batch of {len(final_submit_batch)} articles to CSV…")

          df = pd.to_DataFrame(final_submit_batch)
          df.to_csv("test_all_flow.csv", index=False)
            # print(f"Submitting remaining batch of {len(final_submit_batch)} articles...")
            # batch_response = requests.post(
            #                       f"{URL}/rest/v1/idx_news",
            #                       json=final_submit_batch,
            #                       headers={
            #                           "apikey": KEY,
            #                           "Authorization": f"Bearer {KEY}",
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