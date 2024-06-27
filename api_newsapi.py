import requests
import json
API_KEY = "442861ec22184f0eb100ceb63a29aa8c"

def fetch_news(api_key, query):
    url = f"https://newsapi.org/v2/everything?q={query}&apiKey={api_key}"
    response = requests.get(url)
    data = response.json()
    return data['articles']

news_articles = fetch_news(API_KEY, "banking")
print(news_articles)

with open('./res/newsAPIbanking.json', 'w') as f:
    json.dump(news_articles, f)