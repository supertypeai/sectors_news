from llm.caller import invoke_structured_llm
from llm.client import TokenUsageLogger

from ..prompts.what_to_watch import WhatToWatchPrompts, WhatToWatch

import json
import logging


LOGGER = logging.getLogger(__name__)


def build_what_to_watch_payload(developments: list[dict]) -> str:
    # Falls back to the same dev_XXX position ids as build_developments_payload
    # when the developments have not been through run_importance yet
    payload = [
        {
            "development_id": development.get("development_id") or f"dev_{position:03d}",
            "event": development["event"],
            "summary": development["summary"],
            "tickers": development["tickers"],
        }
        for position, development in enumerate(
            developments, start=1
        )
    ]

    return json.dumps(payload, ensure_ascii=False, indent=2)


def current_watch_items(current_issue: dict | None) -> list[dict]:
    if current_issue is None:
        return []

    return [
        item
        for item in current_issue.get("what_to_watch", [])
        if item.get("id")
    ]


def build_current_items_payload(current_issue: dict | None) -> str:
    payload = [
        {
            "id": item["id"],
            "sort_date": item["sort_date"],
            "timing_label": item["timing_label"],
            "title": item["title"],
            "tickers": item["tickers"],
        }
        for item in current_watch_items(current_issue)
    ]

    return json.dumps(payload, ensure_ascii=False, indent=2)


def sources_of(source_developments: list[dict]) -> dict:
    return {
        "tickers": sorted({
            ticker
            for development in source_developments
            for ticker in development["tickers"]
        }),
        "supporting_news_ids": sorted({
            news_id
            for development in source_developments
            for news_id in development.get("supporting_news_ids", [])
        }),
    }


# The item to show, with its tickers and article ids, or None to drop it, with
# the reason either way. An item the model kept unchanged takes the current
# item's date and words, so readers see the same row. One kept with no
# development restating it takes the current item's tickers and articles
def decide_item(
    item: dict,
    source_developments: list[dict],
    current_by_id: dict[str, dict],
    matched_ids: set[str],
    as_of_date: str,
) -> tuple[dict | None, str]:
    match_id = item.get("same_as_current_item")
    current_item = current_by_id.get(match_id)

    if current_item is None or match_id in matched_ids:
        if not source_developments:
            return None, f"dropped: unknown ids {item['development_ids']}"

        return {**item, **sources_of(source_developments)}, "new item"

    if item.get("changes_current_item") and source_developments:
        decided = {**item}
        decision = "rewritten: date or terms changed"
    else:
        decided = {
            **item,
            "sort_date": current_item["sort_date"],
            "timing_label": current_item["timing_label"],
            "title": current_item["title"],
        }
        decision = "kept"

    if decided["sort_date"] <= as_of_date:
        return None, "dropped: its date has passed"

    if source_developments:
        decided.update(sources_of(source_developments))
    else:
        decided["tickers"] = current_item["tickers"]
        decided["supporting_news_ids"] = current_item["supporting_news_ids"]
        decision += ", no development restates it"

    return decided, decision


def check_what_to_watch_result(
    development_ids: set[str],
    as_of: str,
    result: dict,
) -> dict:
    as_of_date = as_of[:10]
    
    item_ids = [
        development_id
        for item in result["items"]
        for development_id in item["development_ids"]
    ]

    sort_dates = [str(item["sort_date"]) for item in result["items"]]

    return {
        "unknown_ids": sorted(set(item_ids) - development_ids),
        "not_after_as_of": sorted(
            sort_date for sort_date in sort_dates if sort_date <= as_of_date
        ),
        "is_sorted": sort_dates == sorted(sort_dates),
        "item_count": len(result["items"]),
    }


def run_what_to_watch_generation(
    developments: list[dict],
    models: list[str],
    as_of: str,
    current_issue: dict | None = None,
    exchange: str = "IDX",
    effort: str = "medium",
    token_usage_logger: TokenUsageLogger | None = None,
) -> dict | None:
    response = invoke_structured_llm(
        pydantic_output=WhatToWatch,
        system_prompt=WhatToWatchPrompts.get_system_prompt(exchange),
        user_prompt=WhatToWatchPrompts.get_user_prompt(),
        log_name="What to Watch",
        input_data={
            "developments": build_what_to_watch_payload(
                developments=developments
            ),
            "current_items": build_current_items_payload(
                current_issue=current_issue
            ),
            "as_of": as_of,
        },
        models=models,
        effort=effort,
        token_usage_logger=token_usage_logger,
    )

    if response is None:
        LOGGER.warning("What to Watch | no response")
        return None

    # The model's selection notes, so a date missing from the list can be traced
    LOGGER.info("What to Watch | explanation: %s", response["explanation"])

    development_by_id = {
        development.get("development_id") or f"dev_{position:03d}": development
        for position, development in enumerate(developments, start=1)
    }

    check = check_what_to_watch_result(
        development_ids=set(development_by_id),
        as_of=as_of,
        result=response,
    )

    current_by_id = {
        item["id"]: item
        for item in current_watch_items(current_issue)
    }
    matched_ids: set[str] = set()
    items = []

    for item in response["items"]:
        item = {**item, "sort_date": str(item["sort_date"])}

        source_developments = [
            development_by_id[development_id]
            for development_id in item["development_ids"]
            if development_id in development_by_id
        ]

        decided, decision = decide_item(
            item=item,
            source_developments=source_developments,
            current_by_id=current_by_id,
            matched_ids=matched_ids,
            as_of_date=as_of[:10],
        )

        if decided is not None and decided.get("same_as_current_item") in current_by_id:
            matched_ids.add(decided["same_as_current_item"])

        LOGGER.info(
            "What to Watch | %s: %s | %s",
            item.get("same_as_current_item") or "-",
            decision,
            (decided or item)["title"],
        )

        if decided is not None:
            items.append(decided)

    # A date readers saw earlier today that is now gone, so it can be checked
    for current_id, current_item in current_by_id.items():
        if current_id not in matched_ids:
            LOGGER.info(
                "What to Watch | %s: dropped from the current list | %s %s",
                current_id,
                current_item["timing_label"],
                current_item["title"],
            )

    items.sort(key=lambda item: item["sort_date"])

    return {
        "explanation": response["explanation"],
        "items": items,
        "check": check,
    }
