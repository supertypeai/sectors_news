from collections import Counter

from llm.caller import invoke_structured_llm
from llm.client import TokenUsageLogger

from ..prompts.group import get_grouping_system_prompt, GROUPING_USER_PROMPT, GroupingResult

import json
import logging


LOGGER = logging.getLogger(__name__)


def check_grouping_result(
    input_news_ids: list[int],
    result: dict,
) -> dict[str, list[int]]:
    grouped_ids = [
        news_id 
        for group in result["groups"] 
        for news_id in group["news_ids"]
    ]

    returned_ids = grouped_ids + result["excluded_news_ids"]
    id_counts = Counter(returned_ids)
    input_id_set = set(input_news_ids)
    
    return {
        "unknown_ids": sorted(set(returned_ids) - input_id_set),
        "duplicated_ids": sorted(
            news_id for news_id, count in id_counts.items() if count > 1
        ),
        "missing_ids": sorted(input_id_set - set(returned_ids)),
    }


def build_articles_payload(
    news_rows: list[dict],
    use_body: bool,
) -> str:
    articles = []

    for news_row in news_rows:
        structured_body = news_row["structured_body"]

        if use_body or not structured_body:
            text = news_row["body"]
        else:
            text = structured_body["lead"]

        articles.append(
            {
                "id": news_row["id"], 
                "title": news_row["title"], 
                "text": text}
        )

    return json.dumps(
        articles, 
        ensure_ascii=False, 
        indent=2
    )


def run_grouping(
    news_records: list[dict],
    models: list[str],
    use_body: bool = False,
    exchange: str = "IDX",
    effort: str = "low",
    token_usage_logger: TokenUsageLogger | None = None,
) -> dict | None:
    formated_news = build_articles_payload(
        news_rows=news_records,
        use_body=use_body
    )

    response = invoke_structured_llm(
        pydantic_output=GroupingResult,
        system_prompt=get_grouping_system_prompt(exchange),
        user_prompt=GROUPING_USER_PROMPT,
        log_name="Grouping",
        input_data={"articles": formated_news},
        models=models,
        effort=effort,
        token_usage_logger=token_usage_logger,
    )

    if response is None:
        LOGGER.warning("Grouping | no response")
        return None

    check = check_grouping_result(
        input_news_ids=[
            news_record["id"] 
            for news_record in news_records
        ],
        result=response,
    )

    return {"result": response, "check": check}


def remove_duplicate_ids(result: dict) -> dict:
    seen_ids = set()
    groups = []

    for group in result["groups"]:
        kept_ids = []
        
        for news_id in group["news_ids"]:
            if news_id in seen_ids:
                continue

            seen_ids.add(news_id)
            kept_ids.append(news_id)
        
        if kept_ids:
            groups.append({**group, "news_ids": kept_ids})

    excluded_news_ids = [
        news_id
        for news_id in result["excluded_news_ids"]
        if news_id not in seen_ids
    ]

    return {
        **result, 
        "groups": groups, 
        "excluded_news_ids": excluded_news_ids
    }
