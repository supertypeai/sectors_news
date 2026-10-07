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
            "as_of": as_of,
        },
        models=models,
        effort=effort,
        token_usage_logger=token_usage_logger,
    )

    if response is None:
        LOGGER.warning("What to Watch | no response")
        return None

    development_by_id = {
        development.get("development_id") or f"dev_{position:03d}": development
        for position, development in enumerate(developments, start=1)
    }

    check = check_what_to_watch_result(
        development_ids=set(development_by_id),
        as_of=as_of,
        result=response,
    )

    items = []

    for item in response["items"]:
        source_developments = [
            development_by_id[development_id]
            for development_id in item["development_ids"]
            if development_id in development_by_id
        ]

        if not source_developments:
            LOGGER.warning(
                "What to Watch | dropped item with unknown ids: %s",
                item["development_ids"],
            )
            continue

        items.append({
            **item,
            "sort_date": str(item["sort_date"]),
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
        })

    return {
        "explanation": response["explanation"],
        "items": items,
        "check": check,
    }
