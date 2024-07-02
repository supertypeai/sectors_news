from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import accuracy_score, classification_report
import re
import pandas as pd
import json

# Opening the source
with open('./data/labeled_articles.json', 'r') as f:
    data = json.load(f)

df = pd.DataFrame(data)
df['text'] = df['title'] + ' ' + df['body']
df = df[['text', 'sector']]

# Text preprocessing function
def preprocess_text(text):
    text = re.sub(r'\W', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    text = text.lower()
    return text

df['text'] = df['text'].apply(preprocess_text)

# Encode the labels
label_encoder = LabelEncoder()
df['sector'] = label_encoder.fit_transform(df['sector'])

# Split the data into training and testing sets
X_train, X_test, y_train, y_test = train_test_split(df['text'], df['sector'], test_size=0.2, random_state=42)

# Convert text data to TF-IDF features
tfidf_vectorizer = TfidfVectorizer(max_features=5000)
X_train_tfidf = tfidf_vectorizer.fit_transform(X_train)
X_test_tfidf = tfidf_vectorizer.transform(X_test)

# Train the model
model = LogisticRegression(max_iter=1000)  # Increase max_iter if the default 100 is not enough for convergence
model.fit(X_train_tfidf, y_train)

# Predict on the test set
y_pred = model.predict(X_test_tfidf)

# Evaluate the model
print(f'Accuracy: {accuracy_score(y_test, y_pred)}')
print(classification_report(y_test, y_pred, target_names=label_encoder.classes_))

# Print the first few rows of the dataframe
print(df.head())
