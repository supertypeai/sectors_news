from datetime import datetime
from pathlib import Path

from .client import SUPABASE_CLIENT

import json
import re
import logging


logger = logging.getLogger(__name__)

DATA_DIR = Path("data")


def get_sectors_data() -> dict[str, any]:
    path = DATA_DIR / "idx/sectors_data.json"
    
    if not path.exists():
        logger.warning(f"{path} not found. Returning empty sectors.")
        return {}
    
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)


def get_sectors_data_sgx() -> dict[str, any]:
    path = DATA_DIR / "sgx/sectors_data_sgx.json"
    
    if not path.exists():
        logger.warning(f"{path} not found. Returning empty sectors.")
        return {}
    
    with open(path, "r", encoding="utf-8") as file:
        return json.load(file)
    

def update_top300() -> list[dict[str, any]]:
    cache_path = DATA_DIR / "idx/top300.json"
    
    # Run update logic only on the 1st of the month
    if datetime.today().day == 1:
        logger.info("Fetching fresh Top 300 companies from Supabase...")
        try:
            response = SUPABASE_CLIENT.table('idx_company_report') \
                .select('symbol') \
                .order('market_cap_rank', desc=False) \
                .limit(300) \
                .execute()
            
            # Save to cache
            with open(cache_path, 'w', encoding="utf-8") as f:
                json.dump(response.data, f)
            
            return response.data
        except Exception as e:
            logger.error(f"Failed to fetch top 300: {e}")
            # Fallback to cache if fetch fails
            pass

    # Load from cache
    if cache_path.exists():
        with open(cache_path, "r", encoding="utf-8") as file:
            return json.load(file)
    
    return []


def build_ticker_index() -> dict[str, str]:
    path = DATA_DIR / "idx/companies.json"
    if not path.exists():
        return {}

    with open(path, 'r', encoding="utf-8") as file:
        companies_data = json.load(file)

    ticker_index = {}
    short_name_threshold = 6  # characters after normalization

    for entry in companies_data.values():
        symbol = entry.get('symbol', '').strip()
        raw_name = entry.get('name', '')

        if not symbol or not raw_name:
            continue

        clean_name = re.sub(r'^\s*PT\s+', '', raw_name, flags=re.IGNORECASE)
        clean_name = re.sub(r'\s*Tbk\.?$', '', clean_name, flags=re.IGNORECASE)
        clean_name = re.sub(r'\s*\(Persero\)\s*', ' ', clean_name, flags=re.IGNORECASE)
        normalized_name = re.sub(r'\s+', ' ', clean_name).strip().lower()

        ticker_index[normalized_name] = symbol

        # If name normalizes to something very short, also index by ticker code
        # so "timah" -> dead end, but "tins" -> TINS.JK works via ticker path
        if len(normalized_name) < short_name_threshold:
            ticker_code = symbol.lower().replace('.jk', '').strip()
            ticker_index[ticker_code] = symbol
            print(f"short name warning: {raw_name!r} normalizes to {normalized_name!r}, "
                  f"added ticker key {ticker_code!r} -> {symbol}")

    return ticker_index


def build_sgx_ticker_index() -> dict[str, str]:
    path = DATA_DIR / "sgx/sgx_companies.json"

    with open(path, 'r', encoding="utf-8") as file:
        companies_data = json.load(file)

    ticker_index = {}
    short_name_threshold = 5

    for entry in companies_data.values():
        symbol = entry.get('symbol', '').strip()
        raw_name = entry.get('name', '')

        if not symbol or not raw_name:
            continue

        clean_name = re.sub(r'\s*Ltd\.?$', '', raw_name, flags=re.IGNORECASE)
        clean_name = re.sub(r'\s*Limited\.?$', '', clean_name, flags=re.IGNORECASE)
        clean_name = re.sub(r'\s*Pte\.?$', '', clean_name, flags=re.IGNORECASE)
        normalized_name = clean_name.strip().lower()

        ticker_index[normalized_name] = symbol

        if len(normalized_name) < short_name_threshold:
            ticker_index[normalized_name] = symbol
            print(f"short name warning: {raw_name!r} normalizes to "
                  f"{normalized_name!r}, keeping as-is -> {symbol}")

    return ticker_index


# if __name__ == '__main__': 
#     build_sgx_ticker_index()