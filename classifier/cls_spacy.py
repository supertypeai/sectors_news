import spacy
import json

# Classification using spacy, with keywords

sectors_keywords = {
    "transportation-logistic": [
        "revolving loan", "logistics", "delivery", "truck", "transportation", "shipping"
    ],
    "infrastructures": [
        "toll road", "construction", "infrastructure", "telecommunication", "refinancing", "civil engineering", 
        "bond", "building", "concession", "expansion", "project"
    ],
    "financials": [
        "share buyback", "capital", "investment", "loan", "debt", "equity", "bank", "IPO", "financing", "bond",
        "acquisition", "subsidiary", "foreign debt", "dividend", "shares", "net foreign volume"
    ],
    "technology": [
        "fintech", "digital", "software", "IT services", "technology", "e-commerce", "shares", "net foreign volume",
        "IPO", "startup", "platform", "internet"
    ],
    "industrials": [
        "production", "facility", "equipment", "industrial", "services", "goods", "manufacturing", "fleet", "vehicle",
        "machinery", "factory", "expansion", "production facility"
    ],
    "properties-real-estate": [
        "property", "real estate", "development", "project", "land", "hotel", "resort", "dividend", "shares", "acquisition",
        "development", "estate", "property developer"
    ],
    "consumer-cyclicals": [
        "media", "entertainment", "retailing", "household", "services", "leisure", "consumer", "e-commerce", "shopping",
        "sales", "dividend", "shares", "purchase"
    ],
    "consumer-non-cyclicals": [
        "food", "beverage", "manufacturer", "dividend", "capital", "acquisition", "grocery", "agriculture", "dairy",
        "consumption", "retail"
    ],
    "energy": [
        "energy", "alternative energy", "oil", "gas", "coal", "LNG", "hydro", "electric", "renewable", "plant", "facility",
        "power"
    ],
    "basic-materials": [
        "materials", "basic materials", "glass", "manufacturer", "pulp", "paper", "detergent", "chemicals", "nickel",
        "mineral", "extraction", "processing", "refinery"
    ],
    "healthcare": [
        "healthcare", "equipment", "provider", "hospital", "pharmaceuticals", "health care research", "IPO", "dividend",
        "medical", "device", "production", "facility"
    ]
}

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

# Load spaCy model
nlp = spacy.load("en_core_web_sm")

# Function to classify news
def classify_news(news, sectors_keywords):
    doc = nlp(news['body'])
    for sector, keywords in sectors_keywords.items():
        for keyword in keywords:
            if keyword.lower() in doc.text.lower():
                return sector
    return "Other"

# Classify each news item
classified_news = []
for news in articles:
    news['sector'] = classify_news(news, sectors_keywords)
    classified_news.append(news)

# Save classified news to JSON
with open("./data/spacy/classified_news.json", "w") as f:
    json.dump(classified_news, f, indent=4)

print("Classified News:", classified_news)
