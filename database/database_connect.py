from datetime import datetime
from supabase import create_client, Client

from config.setup import SUPABASE_KEY, SUPABASE_URL

import json
import re 


if not SUPABASE_URL or not SUPABASE_KEY:
    raise Exception("Supabase key and URL must be set")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

sectors_data = {}

with open("./data/sectors_data.json", "r") as sectors_file:
    sectors_data = json.load(sectors_file)

if datetime.today().day in [1]:
    response = supabase.table('idx_company_report') \
      .select('symbol') \
      .order('market_cap_rank', desc=False) \
      .limit(300) \
      .execute()

    with open('./data/top300.json', 'w') as top_300:
        top_300.write(json.dumps(response.data))
    
top300_data = {}

with open("./data/top300.json", "r") as top_300:
    top300_data = json.load(top_300)

# Create indexing for ticker
pipeline_filtered = 'data/companies.json'
with open(pipeline_filtered, 'r') as file:
    datas = json.load(file)

ticker_index = {}
for value in datas.values():
    ticker = value.get('symbol').strip().lower()
    name = value.get('name')
    # remove leading "PT" and trailing "Tbk"/"Tbk."
    name = re.sub(r'^\s*PT\s+', '', name, flags=re.IGNORECASE) 
    # remove 'Tbk' or 'Tbk.' at the end, along with extra spaces/dots
    name = re.sub(r'\s*Tbk\.?$', '', name, flags=re.IGNORECASE).strip()
    # remove "(Persero)" anywhere
    name = re.sub(r'\s*\(Persero\)\s*', ' ', name, flags=re.IGNORECASE)
    name = name.strip().lower()
    ticker_index[name] = ticker