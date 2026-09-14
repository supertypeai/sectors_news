from functools import lru_cache
from pathlib import Path

from scraper_engine.database.client import SUPABASE_CLIENT
from .json_helpers import read_json

import re


DATA_DIR = Path("data")


SGX_SYMBOL_SUFFIX = ".SI"


def is_raw_ticker(text: str) -> bool:
    cleaned = text.strip()
    return bool(re.match(r"^[A-Z]{2,6}$", cleaned))


def normalize_idx_company_name(raw: str) -> str:
    name = re.sub(r"^\s*PT\s+", "", raw, flags=re.IGNORECASE)
    name = re.sub(r"\s*Tbk\.?$", "", name, flags=re.IGNORECASE)
    name = re.sub(r"\s*\(Persero\)\s*", " ", name, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", name).strip().lower()


def normalize_sgx_company_name(raw: str) -> str:
    name = re.sub(r"\s*Ltd\.?$", "", raw, flags=re.IGNORECASE)
    name = re.sub(r"\s*Limited\.?$", "", name, flags=re.IGNORECASE)
    name = re.sub(r"\s*Pte\.?$", "", name, flags=re.IGNORECASE)
    name = re.sub(r"\s*Bhd\.?$", "", name, flags=re.IGNORECASE)
    name = re.sub(r"\s*\(Holdings\)\s*$", "", name, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", name).strip().lower()


@lru_cache(maxsize=1)
def build_idx_ticker_index() -> dict[str, str]:
    path = DATA_DIR / "idx/companies.json"
    if not path.exists():
        return {}

    companies_data = read_json(path)

    ticker_index = {}
    short_name_threshold = 6

    for entry in companies_data.values():
        symbol = entry.get("symbol", "").strip()
        raw_name = entry.get("name", "")

        if not symbol or not raw_name:
            continue

        normalized_name = normalize_idx_company_name(raw_name)
        ticker_index[normalized_name] = symbol

        if len(normalized_name) < short_name_threshold:
            ticker_code = symbol.lower().replace(".jk", "").strip()
            ticker_index[ticker_code] = symbol
            print(
                f"short name warning: {raw_name!r} normalizes to "
                f"{normalized_name!r}, added ticker key {ticker_code!r} -> {symbol}"
            )

    return ticker_index


@lru_cache(maxsize=1)
def build_sgx_ticker_index() -> dict[str, str]:
    path = DATA_DIR / "sgx/sgx_companies.json"
    companies_data = read_json(path)

    ticker_index = {}
    short_name_threshold = 5

    for entry in companies_data.values():
        symbol = entry.get("symbol", "").strip()
        raw_name = entry.get("name", "")

        if not symbol or not raw_name:
            continue

        normalized_name = normalize_sgx_company_name(raw_name)
        ticker_index[normalized_name] = symbol

        if len(normalized_name) < short_name_threshold:
            ticker_index[normalized_name] = symbol
            print(
                f"short name warning: {raw_name!r} normalizes to "
                f"{normalized_name!r}, keeping as-is -> {symbol}"
            )

    return ticker_index


def get_top_200_symbols() -> set[str]:
    response = (
        SUPABASE_CLIENT
        .table("sgx_company_report")
        .select("symbol, market_cap")
        .order("market_cap", desc=True)
        .limit(200)
        .execute()
    )

    response_reit = (
        SUPABASE_CLIENT
        .table("sgx_reit_profile")
        .select("symbol")
        .execute()
    )

    record_db = response.data + response_reit.data

    return {
        record["symbol"]
        for record in record_db
    }


def add_sgx_suffix(symbols: list[str] | None) -> list[str]:
    if not symbols:
        return symbols if symbols is not None else []

    return [
        symbol
        if symbol.upper().endswith(SGX_SYMBOL_SUFFIX)
        else f"{symbol}{SGX_SYMBOL_SUFFIX}"
        for symbol in symbols
    ]
