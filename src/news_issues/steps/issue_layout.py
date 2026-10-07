from datetime import datetime, timedelta

from ..utils.constant import DAILY_DATA_TABLES
from ..utils.db import get_db


def get_market_caps(
    tickers: list[str],
    as_of_date: str,
    exchange: str = "IDX",
    lookback_days: int = 7,
) -> dict[str, int]:
    if not tickers:
        return {}

    # Look back a few days so weekends and holidays still have a closing value
    start_date = (
        datetime.strptime(as_of_date, "%Y-%m-%d") - timedelta(days=lookback_days)
    ).strftime("%Y-%m-%d")

    records = get_db(
        table=DAILY_DATA_TABLES[exchange],
        columns="symbol, date, market_cap",
        query=lambda query: (
            query
            .in_("symbol", sorted(set(tickers)))
            .gte("date", start_date)
            .lte("date", as_of_date)
            .order("date", desc=False)
        ),
    )

    return {
        record["symbol"]: record["market_cap"]
        for record in records
        if record["market_cap"] is not None
    }


def development_market_cap(
    development: dict,
    market_caps: dict[str, int],
) -> int:
    return max(
        (
            market_caps.get(ticker, 0) 
            for ticker in development["tickers"]
        ),
        default=0,
    )


def build_issue_layout(
    developments: list[dict],
    result: dict,
    market_caps: dict[str, int] | None = None,
    section_cap: int = 4,
    minimum_lead_importance: int = 3,
    minimum_story_importance: int = 3,
    minimum_other_importance: int = 4,
) -> dict:
    market_caps = market_caps or {}

    developments_by_id = {
        f"dev_{position:03d}": development
        for position, development in enumerate(developments, start=1)
    }

    lead_id = result["lead_development_id"]

    ranked_assignments = sorted(
        result["assignments"],
        # Equal scores go to the bigger company, then to the wider coverage
        key=lambda assignment: (
            assignment["importance"],
            development_market_cap(
                developments_by_id[assignment["development_id"]], market_caps
            ),
            len(developments_by_id[assignment["development_id"]]["supporting_news_ids"]),
        ),
        reverse=True,
    )

    importance_by_id = {
        assignment["development_id"]: assignment["importance"]
        for assignment in ranked_assignments
    }

    # A lead below the minimum means a quiet day, unless a stronger story exists
    lead_id = result["lead_development_id"]

    if importance_by_id.get(lead_id, 0) < minimum_lead_importance:
        lead_id = None

    lead = None
    sections = {}
    flash = []

    for assignment in ranked_assignments:
        development_id = assignment["development_id"]
        development = developments_by_id[development_id]
        section = assignment["section"]

        if development_id == lead_id:
            lead = {**development, "section": section}
            continue

        # Stories with no section need a higher score to earn a slot
        required_importance = (
            minimum_other_importance
            if section == "other"
            else minimum_story_importance
        )

        section_stories = sections.setdefault(section, [])

        is_story = (
            assignment["importance"] >= required_importance
            and len(section_stories) < section_cap
        )

        if is_story:
            section_stories.append(development)

        else:
            flash.append(development)

    sections = {
        section: stories 
        for section, stories in sections.items() 
        if stories
    }

    return {
        "lead": lead, 
        "sections": sections, 
        "flash": flash
    }
