from datetime import date, datetime, timezone, timedelta
from zoneinfo import ZoneInfo

from .constant import MARKET_TIME_ZONES, ISSUE_WINDOW_DAYS, ISSUE_CUTOFF_TIMES


def build_cutoff_utc(
    issue_date: date,
    exchange: str,
) -> str:
    local_cutoff = datetime.combine(
        issue_date,
        ISSUE_CUTOFF_TIMES[exchange],
        tzinfo=ZoneInfo(MARKET_TIME_ZONES[exchange]),
    )

    return local_cutoff.astimezone(
        timezone.utc
    ).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_update_end_utc(
    issue_date: date,
    exchange: str,
) -> str:
    # An update reads every article inserted so far, so a slow scrape's tail
    # still lands, but never past the cutoff the final run stops at
    return min(build_now_utc(), build_cutoff_utc(issue_date, exchange))


def is_before_cutoff(
    issue_date: date,
    exchange: str,
) -> bool:
    # A run that starts before the cutoff is an update, even when the queue held
    # it late: only a run after the cutoff has every article of the day inserted
    return build_now_utc() < build_cutoff_utc(issue_date, exchange)


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
