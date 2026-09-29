from datetime import date, datetime, timedelta

from ..constant import MARKETS


def get_session_slots(market: str, day: date) -> list[tuple[str, datetime]]:
    if day.weekday() >= 5:
        return []

    market_config = MARKETS[market]

    return [
        (session, datetime.combine(day, session_time, tzinfo=market_config["timezone"]))
        for session, session_time in market_config["sessions"]
    ]


def get_slot_before(market: str, moment: datetime) -> datetime:
    """
    Latest session close strictly before `moment`
    """
    day = moment.astimezone(MARKETS[market]["timezone"]).date()

    while True:
        for _, slot in reversed(get_session_slots(market, day)):
            if slot < moment:
                return slot

        day -= timedelta(days=1)


def build_brief_windows(
    market: str,
    start_window: datetime,
    until: datetime,
) -> list[dict]:
    """
    Contiguous windows for every session close in (start_window, until].
    Each window starts where the previous one ended, so no article falls between two briefs
    """
    brief_windows = []
    
    day = start_window.astimezone(MARKETS[market]["timezone"]).date()
    last_day = until.astimezone(MARKETS[market]["timezone"]).date()

    while day <= last_day:
        for session, slot in get_session_slots(market, day):
            if start_window < slot <= until:
                brief_windows.append({
                    "market": market,
                    "market_date": day,
                    "session": session,
                    "start_window": start_window,
                    "end_window": slot,
                })
                start_window = slot

        day += timedelta(days=1)

    return brief_windows
