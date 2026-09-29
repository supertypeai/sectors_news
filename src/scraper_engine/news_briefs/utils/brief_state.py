from pathlib import Path

from ..constant import PREVIOUS_BRIEFS_FOR_RECONCILE, STATE_DIR
from .brief_helper import write_json_output

import json


def get_state_path(market: str) -> Path:
    return STATE_DIR / market / "state.json"


def read_state(market: str) -> dict | None:
    state_path = get_state_path(market)

    if not state_path.exists():
        return None

    with state_path.open() as file:
        return json.load(file)


def write_state(market: str, recent_briefs: list[dict]) -> None:
    """
    The last brief's end_window is the watermark the next run starts from;
    the recent briefs' topics are what the next run reconciles against.
    """
    write_json_output(
        output_path=get_state_path(market),
        records={
            "market": market,
            "end_window": recent_briefs[-1]["end_window"],
            "recent_briefs": [
                {
                    "market_date": brief["market_date"],
                    "session": brief["session"],
                    "start_window": brief["start_window"],
                    "end_window": brief["end_window"],
                    "development_topics": brief["development_topics"],
                }
                for brief in recent_briefs
            ],
        },
    )


def get_previous_topic_states(recent_briefs: list[dict]) -> list[dict]:
    return [
        topic
        for brief in recent_briefs[-PREVIOUS_BRIEFS_FOR_RECONCILE:]
        for topic in brief["development_topics"]["topics"]
    ]
