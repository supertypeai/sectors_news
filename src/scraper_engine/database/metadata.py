from pathlib import Path

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