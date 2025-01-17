from transformers import pipeline
import json

# Load a pre-trained BERT model for text classification
classifier = pipeline("zero-shot-classification", model="facebook/bart-large-mnli")

# Function to classify news using BERT
def classify_news_bert(news, sectors):
    result = classifier(news['body'], sectors)
    return result['labels'][0]  # The top predicted sector

# Define sectors
sectors = []
sectors_keywords = [
    "transportation-logistic",
    "infrastructures",
    "financials",
    "technology",
    "industrials",
    "properties-real-estate",
    "consumer-cyclicals",
    "consumer-non-cyclicals",
    "energy",
    "basic-materials",
    "healthcare"
]

# Function to load JSON data from a file
def load_json(filename):
    with open(filename, 'r', encoding='utf-8') as file:
        return json.load(file)

# Function to save JSON data to a file
def save_json(data, filename):
    with open(filename, 'w', encoding='utf-8') as file:
        json.dump(data, file, indent=4)

# Load the articles data
raw_data = load_json('./data/idnarticles9.json')

# Flatten nested lists
def flatten_articles(raw_data):
    articles = []
    def recursive_extract(data):
        if isinstance(data, dict) and 'title' in data:
            articles.append(data)
        elif isinstance(data, list):
            for item in data:
                recursive_extract(item)
        elif isinstance(data, dict):
            for key, value in data.items():
                recursive_extract(value)

    recursive_extract(raw_data)
    return articles

# Flatten the articles data
articles = flatten_articles(raw_data)

# Classify each news item
classified_news = []
for news in articles:
    news['sector'] = classify_news_bert(news, sectors)
    classified_news.append(news)

# Save classified news to JSON
with open("./data/transformer/classified_news_bert.json", "w") as f:
    json.dump(classified_news, f, indent=4)

print("Classified News using BERT:", classified_news)
