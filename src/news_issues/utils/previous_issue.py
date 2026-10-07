from datetime import date

from .issue_window import build_issue_window
from .json_io import output_path, read_json, write_json


PREVIOUS_ISSUE_NAME = "previous_issue"


def to_previous_story(story: dict) -> dict:
    # The importance step only reads these fields to spot stories already covered
    return {
        "event": story["event"],
        "headline": story["headline"],
        "blurb": story["blurb"],
        "tickers": story["tickers"],
    }


def to_previous_issue(
    display_result: dict,
    issue_date: str,
    window_start: str,
    window_end: str,
) -> dict:
    return {
        "issue_date": issue_date,
        "window_start": window_start,
        "window_end": window_end,
        "lead": (
            to_previous_story(display_result["lead"])
            if display_result["lead"] is not None
            else None
        ),
        "sections": {
            section: [
                to_previous_story(story) 
                for story in stories
            ]
            for section, stories in display_result["sections"].items()
        },
    }


def resolve_issue_window(
    issue_date: date,
    exchange: str,
    previous_issue: dict | None,
) -> tuple[str, str]:
    window_start, window_end = build_issue_window(issue_date, exchange)

    # Start where the previous issue stopped, so a missed run's articles roll into this issue
    if previous_issue is not None and previous_issue.get("window_end"):
        window_start = previous_issue["window_end"]

    return window_start, window_end


def is_already_built(
    issue_date: date,
    previous_issue: dict | None,
) -> bool:
    if previous_issue is None or not previous_issue.get("issue_date"):
        return False

    return previous_issue["issue_date"] >= issue_date.isoformat()


def load_previous_issue(exchange: str) -> dict | None:
    if not output_path(
        name=PREVIOUS_ISSUE_NAME, 
        exchange=exchange
    ).exists():
        return None

    return read_json(
        name=PREVIOUS_ISSUE_NAME, 
        exchange=exchange
    )


def save_previous_issue(
    previous_issue: dict,
    exchange: str,
) -> None:
    write_json(
        data=previous_issue,
        name=PREVIOUS_ISSUE_NAME,
        exchange=exchange,
    )
