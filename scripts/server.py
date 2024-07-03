import requests
from dotenv import load_dotenv
import os
import json
import argparse

load_dotenv()

url = os.getenv('DATABASE_URL')
KEY = os.getenv('DB_KEY')

def post_articles(url, jsonfile):
  with open(f'./data/{jsonfile}.json', 'r') as f:
    articles = json.load(f)

  headers = {
    'Authorization': f'Bearer {KEY}',
    'Content-Type': 'application/json'
  }

  response = requests.post(url + '/articles/list', json=articles, headers=headers)

  if response.status_code == 200:
    print('Success:', response.json())
  else:
    print('Failed:', response.status_code, response.text)

def post_article(url, jsonfile):
  with open(f'./data/{jsonfile}.json', 'r') as f:
    article = json.load(f)

  if isinstance(article, list):
    article = article[0]
  
  headers = {
    'Authorization': f'Bearer {KEY}',
    'Content-Type': 'application/json'
  }

  response = requests.post(url + '/articles', json=article, headers=headers)

  if response.status_code == 200:
    print('Success:', response.json())
  else:
    print('Failed:', response.status_code, response.text)

def main():

  parser = argparse.ArgumentParser(description="Script for posting articles to database server")
  parser.add_argument("filename", type=str, default="labeled_articles")
  parser.add_argument("--list", action='store_true', help="Flag to indicate posting a list of articles")

  args = parser.parse_args()

  filename = args.filename

  if args.list:
    post_articles(url, filename)
  else:
    post_article(url, filename)

if __name__ == "__main__":
  main()

# Sample usage
# python ./scripts/server.py filename --list