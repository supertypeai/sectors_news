from datetime import date, datetime, time, timezone, timedelta
from zoneinfo import ZoneInfo

from .constant import MARKET_TIME_ZONES, ISSUE_WINDOW_DAYS


def build_cutoff_utc(
    issue_date: date,
    exchange: str,
    cutoff_time: time = time(17, 30),
) -> str:
    local_cutoff = datetime.combine(
        issue_date,
        cutoff_time,
        tzinfo=ZoneInfo(MARKET_TIME_ZONES[exchange]),
    )

    return local_cutoff.astimezone(
        timezone.utc
    ).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_issue_window(
    issue_date: date,
    exchange: str,
) -> tuple[str, str]:
    window_start = build_cutoff_utc(
        issue_date - timedelta(
            days=ISSUE_WINDOW_DAYS[exchange]
        ), exchange
    )
    window_end = build_cutoff_utc(issue_date, exchange)

    return window_start, window_end


def build_issue_dates(
    first_issue_date: str,
    issue_count: int,
    exchange: str,
) -> list[date]:
    # Issues are dated on their cutoff: daily for IDX, Friday for SGX
    first_date = date.fromisoformat(first_issue_date)

    return [
        first_date + timedelta(
            days=issue_index * ISSUE_WINDOW_DAYS[exchange]
        )
        for issue_index in range(issue_count)
    ]
