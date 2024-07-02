import requests
import pandas as pd
import altair as alt
import json
import dotenv
import os

dotenv.load_dotenv()

def write_json(jsontext, filename):
    with open(f'../data/{filename}.json', 'w') as f:
      json.dump(jsontext, f)

API_KEY = os.getenv('API_KEY')
url = "https://api.sectors.app/v1/subsectors/"

headers = {
  "Authorization": API_KEY
}

response = requests.get(url, headers=headers)

if response.status_code == 200:
  data_all_subsectors = response.json()
else:
  print(response.status_code)

print(data_all_subsectors)
write_json(data_all_subsectors, "subsectors")