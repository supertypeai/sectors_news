from pathlib import Path
from supabase import create_client

from scraper_engine.config.conf import SUPABASE_KEY, SUPABASE_URL
from scraper_engine.database.client import SUPABASE_CLIENT
from scraper_engine.llm.client import TokenUsageLogger
from ..constant import BRIEFS_TABLE

import json
import logging


LOGGER = logging.getLogger(__name__)


def get_db(table: str, columns: str = "*", query=None):
    supabase_client = create_client(
        supabase_key=SUPABASE_KEY,
        supabase_url=SUPABASE_URL
    )

    db_query = (
        supabase_client
        .table(table)
        .select(columns)
    )

    if table == "idx_news":
        db_query = db_query.not_.ilike(
            "source",
            "https://www.idx.co.id/StaticData/NewsAndAnnouncement/ANNOUNCEMENTSTOCK/From_KSEI/%",
        )

    elif table == "sgx_news":
        db_query = db_query.not_.ilike(
            "source",
            "https://links.sgx.com/1.0.0/corporate-announcements/%",
        )

    if query:
        db_query = query(db_query)

    response = db_query.execute()

    records = response.data

    return records


def to_news_brief_row(brief_result: dict) -> dict:
    market_brief = brief_result.get("market_brief") or {}
    what_to_watch = brief_result.get("what_to_watch") or {}

    return {
        "market": brief_result["market"],
        "market_date": brief_result["market_date"],
        "session": brief_result["session"],
        "market_pulse": market_brief.get("briefs") or [],
        "what_to_watch": what_to_watch.get("items") or [],
        "policy_news": brief_result.get("policies") or [],
    }


def upsert_news_brief(brief_result: dict) -> None:
    (
        SUPABASE_CLIENT
        .table(BRIEFS_TABLE)
        .upsert(
            to_news_brief_row(brief_result),
            on_conflict="market,market_date,session",
        )
        .execute()
    )


def write_json_output(output_path: Path, records) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_suffix(f"{output_path.suffix}.tmp")

    with temporary_path.open("w") as file:
        json.dump(records, file, indent=2)

    temporary_path.replace(output_path)


def log_total_cost(token_usage_logger: TokenUsageLogger) -> None:
    total_cost = sum(
        cost
        for cost in token_usage_logger.request_costs
        if cost is not None
    )

    LOGGER.info(
        "Total reported cost: $%.8f USD | completed requests: %d | missing cost: %d",
        total_cost,
        len(token_usage_logger.request_costs),
        token_usage_logger.request_costs.count(None),
    )
