from datetime import datetime
from pathlib import Path

from .client import SUPABASE_CLIENT

import json
import re
import logging


logger = logging.getLogger(__name__)

DATA_DIR = Path("data")


def get_sectors_data() -> dict[str, any]:
    path = DATA_DIR / "sectors_data.json"
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
    
    # Iterate over values (assuming companies_data is a dict of dicts)
    for entry in companies_data.values():
        symbol = entry.get('symbol', '').strip()
        raw_name = entry.get('name', '')
        
        if not symbol or not raw_name:
            continue

        # Clean the company name
        # 1. Remove leading PT
        clean_name = re.sub(r'^\s*PT\s+', '', raw_name, flags=re.IGNORECASE)
        # 2. Remove trailing Tbk
        clean_name = re.sub(r'\s*Tbk\.?$', '', clean_name, flags=re.IGNORECASE)
        # 3. Remove (Persero)
        clean_name = re.sub(r'\s*\(Persero\)\s*', ' ', clean_name, flags=re.IGNORECASE)
        
        normalized_name = clean_name.strip().lower()
        ticker_index[normalized_name] = symbol

    return ticker_index


def build_sgx_ticker_index() -> dict[str, str]:
    if datetime.today().day in [1, 15]:
        response = (
            SUPABASE_CLIENT
            .table('sgx_company_report')
            .select('symbol', 'name', 'sub_sector', 'sector')
            .execute()
        )

        lookup = {}
        for item in response.data:
            lookup[item['symbol']] = {
                'symbol': item['symbol'],
                'name': item['name'],
                'sub_sector': item['sub_sector']
            }
        path = DATA_DIR / "sgx_companies.json"
        with open(path, 'w') as file:
            json.dump(lookup, file, indent=4)

    path = DATA_DIR / "sgx/sgx_companies.json"
   
    with open(path, 'r', encoding="utf-8") as file:
        companies_data = json.load(file)

    ticker_index = {}
    
    # create lookup with cleaned names
    for entry in companies_data.values():
        symbol = entry.get('symbol', '').strip()
        raw_name = entry.get('name', '')
        
        if not symbol or not raw_name:
            continue

        # Clean the company name
        # Remove trailing Ltd
        clean_name = re.sub(r'\s*Ltd\.?$', '', raw_name, flags=re.IGNORECASE)
        
        normalized_name = clean_name.strip().lower()
        ticker_index[normalized_name] = symbol

    return ticker_index