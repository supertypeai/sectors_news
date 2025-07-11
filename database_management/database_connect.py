from datetime import datetime
from supabase import create_client, Client
import os
import json
from dotenv import load_dotenv 

load_dotenv(override=True)

SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")

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