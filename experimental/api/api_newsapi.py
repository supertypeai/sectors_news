import requests
import json
import os
import dotenv

dotenv.load_dotenv()

API_KEY = os.getenv('API_KEY_NEWSAPI')

def fetch_news(api_key, query):
    url = f"https://newsapi.org/v2/everything?q={query}&apiKey={api_key}"
    response = requests.get(url)
    data = response.json()
    return data['articles']

news_articles = fetch_news(API_KEY, "banking")
print(news_articles)

with open('../data/newsAPIbanking.json', 'w') as f:
    json.dump(news_articles, f)