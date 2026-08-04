from datetime import datetime
from pathlib import Path

from scraper_engine.database.client import SUPABASE_CLIENT

import json
import re
import logging


logger = logging.getLogger(__name__)

DATA_DIR = Path("data")


def open_json(path: str | Path) -> dict | list:
    json_path = Path(path)

    with json_path.open("r", encoding="utf-8") as file:
        return json.load(file)


def write_json(path: str | Path, payload: dict | list) -> None:
    json_path = Path(path)

    with json_path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, indent=2)


def get_sectors_data() -> dict[str, any]:
    path = DATA_DIR / "idx/sectors_data.json"
    
    if not path.exists():
        logger.warning(f"{path} not found. Returning empty sectors.")
        return {}
    
    return open_json(path)


def get_sectors_data_sgx() -> dict[str, any]:
    path = DATA_DIR / "sgx/sectors_data_sgx.json"
    
    if not path.exists():
        logger.warning(f"{path} not found. Returning empty sectors.")
        return {}
    
    return open_json(path)


def build_ticker_index() -> dict[str, str]:
    path = DATA_DIR / "idx/companies.json"
    if not path.exists():
        return {}

    companies_data = open_json(path)

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

    companies_data = open_json(path)

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


def convert_to_kebab(sub_sector: str, is_idx: bool = True) -> str:
    if is_idx: 
        return (
            sub_sector
            .replace("&", "")
            .replace(",", "")
            .replace("  ", " ")
            .replace(" ", "-")
            .lower()
        )
    
    result = (
        sub_sector
        .replace("&", "")
        .replace(",", "")
        .replace("  ", " ")
        .replace(" ", "-")
        .lower()
    )

    return re.sub(r'-+', '-', result)

def extract_first_sentences(text: str, count: int = 2) -> str:
    parts = text.split('.')

    if len(parts) <= count:
        return text.strip()
    
    extracted = parts[:count]
    result = '. '.join(extracted) + '.'

    return result 

def load_subsector_data_idx() -> tuple[str, set[str]]:
    path = DATA_DIR / "idx/subsectors_data.json"

    if datetime.today().day in [1, 15]:
        response = (
            SUPABASE_CLIENT
            .table("idx_subsector_metadata")
            .select("slug, description")
            .execute()
        )

        subsectors = {row["slug"]: row["description"] for row in response.data}

        write_json(path, subsectors)

    subsectors = open_json(path)

    # Extract only the first two sentences
    subsector_clean = {}

    for key, value in subsectors.items():
        clean_value = extract_first_sentences(value)
        subsector_clean[key] = clean_value 
    
    subsector_string = "\n\n".join(
        [
            f"{key}:{value}" for key, value in subsector_clean.items()
        ]
    )

    result = (subsector_string, set(subsectors.keys()))

    return result

def load_subsector_data_sgx() -> dict:
    return open_json(DATA_DIR / "sgx/subsectors_data_sgx.json")

def load_tag_data() -> tuple[list, str]:
    tag_data = open_json(DATA_DIR / "unique_tags.json")
    tags = tag_data.get("tags", [])
    
    full_tags = '\n\n'.join(
        f"{tag.get('name')} : {tag.get('description')}" 
        for tag in tags
    )
    
    return tags, full_tags

def load_company_data_idx() -> dict[str, dict[str, str]]:
    path = DATA_DIR / "idx/companies.json"

    if datetime.today().day in [1, 15]:
        response = (
            SUPABASE_CLIENT.table("idx_company_profile")
            .select("symbol, company_name, sub_sector_id")
            .execute()
        )

        subsector_response = (
            SUPABASE_CLIENT.table("idx_subsector_metadata")
            .select("sub_sector_id, sub_sector")
            .execute()
        )

        subsector_data = {
            row["sub_sector_id"]: row["sub_sector"]
            for row in subsector_response.data
        }

        company = {}

        for row in response.data:
            company[row["symbol"]] = {
                "symbol": row["symbol"],
                "name": row["company_name"],
                "sub_sector": convert_to_kebab(
                    subsector_data[row["sub_sector_id"]], 
                    True
                ),
            }

        write_json(path, company)

    return open_json(path)
    
def load_company_data_sgx() -> dict[str, dict[str, str]]:
    path = DATA_DIR / "sgx/sgx_companies.json"

    refresh_day = datetime.today().day in {1, 15}

    if refresh_day:
        response = (
            SUPABASE_CLIENT
            .table("sgx_companies")
            .select("symbol", "name", "sub_sector", "sector")
            .eq('is_suspended', False)
            .eq('is_active', True)
            .execute()
        )

        company = {
            item["symbol"]: {
                "symbol": item["symbol"],
                "name": item["name"],
                "sub_sector": convert_to_kebab(
                    item["sub_sector"], False
                ),
                "sector": convert_to_kebab(
                    item["sector"], False
                )
            }
            for item in response.data
        }

        write_json(path, company)

    return open_json(path)


