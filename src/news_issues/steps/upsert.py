from datetime import date

from scraper_engine.database.client import SUPABASE_CLIENT

from ..utils.issue_window import build_issue_window
from ..utils.json_io import read_json

import logging


LOGGER = logging.getLogger(__name__)


def upsert_data(
    exchange: str,
    data_path: str = "final_data_clean",
    issue_date: date | None = None,
) -> None:
    final_data = read_json(data_path, exchange)

    # Older files carry no window, so rebuild the fixed one from the issue date
    if "window_end" not in final_data:
        window_start, window_end = build_issue_window(issue_date, exchange)

        final_data = {
            **final_data,
            "issue_date": issue_date.isoformat(),
            "window_start": window_start,
            "window_end": window_end,
        }

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
