from collections.abc import Callable
from supabase import create_client

from config.env import SUPABASE_KEY, SUPABASE_URL


def get_db(
    table: str,
    columns: str = "*",
    query: Callable | None = None,
) -> list[dict]:
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
