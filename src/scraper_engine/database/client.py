from supabase import create_client, Client
from scraper_engine.config.conf import SUPABASE_KEY, SUPABASE_URL  

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("Supabase key and URL must be set in configuration.")

SUPABASE_CLIENT: Client = create_client(SUPABASE_URL, SUPABASE_KEY)