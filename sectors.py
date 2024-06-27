import requests
import pandas as pd
import altair as alt
import json

def write_json(jsontext, filename):
    with open(f'./res/{filename}.json', 'w') as f:
      json.dump(jsontext, f)

API_KEY = "65d503ed8197ff9546d774e1557981bfb184830d8f8c93f261e6517507dc5a52"
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