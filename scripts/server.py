import requests
from dotenv import load_dotenv
import os
import json
import argparse

load_dotenv()

URL = os.environ.get('DATABASE_URL')
KEY = os.environ.get('DB_KEY')

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

def post_source(jsonfile):
  with open(f'./data/{jsonfile}.json', 'r') as f:
    articles = json.load(f)

  headers = {
    'Authorization': f'Bearer {KEY}',
    'Content-Type': 'application/json'
  }
  
  
  if isinstance(articles, list):
    
    all_articles_db = requests.get(URL + '/articles', headers=headers).json()
    links = []
    for article_db in all_articles_db:
      if article_db['source'] not in links:
        links.append(article_db['source'])
    # print(links)
    
    submit_article = []
    for article in articles:
      if article['source'] not in links:
        response = requests.post(URL + '/url-article', json=article, headers=headers)
    

        if response.status_code == 200:
          print('Inference Success:', response.json()['source'])
          submit_article.append(response.json())
          links.append(article['source'])
        else:
          print('Inference Failed:', response.status_code, response.text)
    # print(submit_article)
      else:
        print("Article already exists")
    
    response = requests.post(URL + '/articles/list', json=submit_article, headers=headers)
    if response.status_code == 200:
      print('Success:', response.json())
      submit_article.append(response.json())
    else:
      print('Failed:', response.status_code, response.text)
        

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