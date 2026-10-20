from datetime import date
from itertools import count

from .issue_window import build_issue_window, build_update_end_utc
from .json_io import output_path, read_json, write_json


PREVIOUS_ISSUE_NAME = "previous_issue"
CURRENT_ISSUE_NAME = "current_issue"


def to_previous_story(
    story: dict,
    story_id: str,
    slot: str,
) -> dict:
    return {
        "id": story_id,
        "slot": slot,
        "event": story["event"],
        "headline": story["headline"],
        "blurb": story["blurb"],
        "tickers": story["tickers"],
        "supporting_news_ids": [news["id"] for news in story["supporting_news"]],
        "copy_decision": story.get("copy_decision"),
    }


def to_watch_item(item: dict, item_id: str) -> dict:
    return {
        "id": item_id,
        "sort_date": item["sort_date"],
        "timing_label": item["timing_label"],
        "title": item["title"],
        "tickers": item["tickers"],
        "supporting_news_ids": [news["id"] for news in item["supporting_news"]],
    }


def to_previous_issue(
    display_result: dict,
    what_to_watch_result: dict | None,
    issue_date: str,
    window_start: str,
    window_end: str,
) -> dict:
    story_numbers = count(1)

    def next_story(story: dict, slot: str) -> dict:
        return to_previous_story(
            story=story,
            story_id=f"cur_{next(story_numbers):02d}",
            slot=slot,
        )

    return {
        "issue_date": issue_date,
        "window_start": window_start,
        "window_end": window_end,
        "lead": (
            next_story(display_result["lead"], "lead")
            if display_result["lead"] is not None
            else None
        ),
        "sections": {
            section: [
                next_story(story, "story")
                for story in stories
            ]
            for section, stories in display_result["sections"].items()
        },
        "flash": [
            next_story(story, "flash")
            for story in display_result["flash"]
        ],
        "what_to_watch": [
            to_watch_item(item, f"wtw_{position:02d}")
            for position, item in enumerate(
                (what_to_watch_result or {}).get("items", []),
                start=1,
            )
        ],
    }


def resolve_issue_window(
    issue_date: date,
    exchange: str,
    previous_issue: dict | None,
    update: bool = False,
) -> tuple[str, str]:
    window_start, window_end = build_issue_window(issue_date, exchange)

    # Start where the previous issue stopped, so a missed run's articles roll into this issue
    if previous_issue is not None and previous_issue.get("window_end"):
        window_start = previous_issue["window_end"]

    # An update during the day ends at the run, the final run at the cutoff
    if update:
        window_end = build_update_end_utc(issue_date, exchange)

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


def load_current_issue(
    issue_date: date,
    exchange: str,
) -> dict | None:
    if not output_path(
        name=CURRENT_ISSUE_NAME,
        exchange=exchange
    ).exists():
        return None

    current_issue = read_json(
        name=CURRENT_ISSUE_NAME,
        exchange=exchange
    )

    # Only an earlier run of this same issue counts, not yesterday's last one
    if current_issue.get("issue_date") != issue_date.isoformat():
        return None

    return current_issue


def save_current_issue(
    current_issue: dict,
    exchange: str,
) -> None:
    write_json(
        data=current_issue,
        name=CURRENT_ISSUE_NAME,
        exchange=exchange,
    )
