from ..utils.db import get_db


def get_data(
    start_date: str,
    end_date: str,
    table: str = "idx_news",
) -> list[dict]:
    records = get_db(
        table=table, 
        columns="id, title, body, structured_body, symbols, sector, sub_sector, source, thumbnail, timestamp",
        query=lambda query: (
            query
            .gte("created_at", start_date)
            .lt("created_at", end_date)
        ),
    )

    return records
