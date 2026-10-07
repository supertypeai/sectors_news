from scraper_engine.database.client import SUPABASE_CLIENT

from ..utils.json_io import read_json

import logging


LOGGER = logging.getLogger(__name__)


def upsert_data(
    exchange: str,
    data_path: str = "final_data_clean",
) -> None:
    final_data = read_json(data_path, exchange)

    row = {
        "market_type": exchange.lower(),
        "issue_date": final_data["issue_date"],
        "window_start": final_data["window_start"],
        "window_end": final_data["window_end"],
        "lead": final_data["lead"],
        "sections": final_data["sections"],
        "flash": final_data["flash"],
        "what_to_watch": final_data["what_to_watch"],
    }

    (
        SUPABASE_CLIENT
        .table("news_issue")
        .upsert(row, on_conflict="market_type,issue_date")
        .execute()
    )

    LOGGER.info(
        "Upserted %s issue for %s", 
        exchange, 
        final_data["issue_date"]
    )
