import torch
from transformers import BertTokenizer, BertForSequenceClassification, AdamW
from torch.utils.data import DataLoader, TensorDataset, RandomSampler
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import classification_report
import pandas as pd
import json

# Load pre-trained BERT tokenizer
tokenizer = BertTokenizer.from_pretrained('bert-base-uncased')

# Opening the source
with open('../data/labeled_articles400.json', 'r') as f:
  data = json.load(f)

df = pd.DataFrame(data)
df['text'] = df['title'] + ' ' + df['body']
df = df[['text', 'sector']]
df = df[df.sector != 'unknown']

# Encode the labels
label_encoder = LabelEncoder()
df['sector'] = label_encoder.fit_transform(df['sector'])
num_labels = len(label_encoder.classes_)

# Load pre-trained BERT model
model = BertForSequenceClassification.from_pretrained('bert-base-uncased', num_labels=num_labels)

# Preprocess data
def preprocess_data(data, tokenizer, max_length=512):
    input_ids = []
    attention_masks = []

    for text in data:
        encoded_data = tokenizer.encode_plus(
            text,
            add_special_tokens=True,
            max_length=max_length,
            pad_to_max_length=True,
            return_attention_mask=True,
            return_tensors='pt'
        )
        input_ids.append(encoded_data['input_ids'])
        attention_masks.append(encoded_data['attention_mask'])

    return torch.cat(input_ids, dim=0), torch.cat(attention_masks, dim=0)

input_ids, attention_masks = preprocess_data(df['text'].values, tokenizer)
labels = torch.tensor(df['sector'].values, dtype=torch.long)

# Create DataLoader
dataset = TensorDataset(input_ids, attention_masks, labels)
batch_size = 16
dataloader = DataLoader(
    dataset,
    sampler=RandomSampler(dataset),
    batch_size=batch_size
)

# Optimizer
optimizer = AdamW(model.parameters(), lr=2e-5, eps=1e-8)

# Training loop
epochs = 4
for epoch in range(epochs):
    model.train()
    total_loss = 0

    for batch in dataloader:
        b_input_ids, b_attention_mask, b_labels = batch

        model.zero_grad()

        outputs = model(b_input_ids, attention_mask=b_attention_mask, labels=b_labels)
        loss = outputs.loss
        total_loss += loss.item()

        loss.backward()
        optimizer.step()

    avg_loss = total_loss / len(dataloader)
    print(f'Epoch {epoch+1}, Loss: {avg_loss}')

# Switch to evaluation mode
model.eval()

predictions, true_labels = [], []

for batch in dataloader:
    b_input_ids, b_attention_mask, b_labels = batch

    with torch.no_grad():
        outputs = model(b_input_ids, attention_mask=b_attention_mask)

    logits = outputs.logits
    predictions.extend(torch.argmax(logits, dim=1).tolist())
    true_labels.extend(b_labels.tolist())

print(classification_report(true_labels, predictions, target_names=label_encoder.classes_))

# Function to predict sector for new articles
def predict_sector(texts):
    model.eval()
    input_ids, attention_masks = preprocess_data(texts, tokenizer)
    dataset = TensorDataset(input_ids, attention_masks)
    dataloader = DataLoader(dataset, batch_size=batch_size)

    predictions = []
    for batch in dataloader:
        b_input_ids, b_attention_mask = batch
        with torch.no_grad():
            outputs = model(b_input_ids, attention_mask=b_attention_mask)
        logits = outputs.logits
        predictions.extend(torch.argmax(logits, dim=1).tolist())
    
    return label_encoder.inverse_transform(predictions)

# Example usage for new articles
new_articles = [
    "SAPX secures revolving loan of IDR 125 billion",
    "Waskita Karya to inject IDR 10 billion for Kapal Betung Toll Road"
]
predicted_sectors = predict_sector(new_articles)
for article, sector in zip(new_articles, predicted_sectors):
    print(f"Article: {article}\nPredicted Sector: {sector}\n")

# Save the model
model.save_pretrained('./model400')
tokenizer.save_pretrained('./model400')

# Load the model
# model = BertForSequenceClassification.from_pretrained('path/to/save/model')
# tokenizer = BertTokenizer.from_pretrained('path/to/save/tokenizer')