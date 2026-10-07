from llm.caller import invoke_structured_llm_async
from llm.client import TokenUsageLogger

from ..utils.constant import CONCURRENCY
from ..prompts.group_generation import Development, get_development_system_prompt, DEVELOPMENT_USER_PROMPT

import json
import asyncio
import logging


LOGGER = logging.getLogger(__name__)


def build_group_payload(
    news_rows: list[dict],
    group_news_ids: list[int],
) -> str:
    rows_by_id = {
        news_row["id"]: news_row 
        for news_row in news_rows
    }
    
    articles = []

    for news_id in group_news_ids:
        news_row = rows_by_id[news_id]
        articles.append(
            {
                "id": news_row["id"],
                "title": news_row["title"],
                "text": news_row["body"],
                "tickers": news_row["symbols"] or [],
            }
        )

    return json.dumps(articles, ensure_ascii=False, indent=2)


def find_unknown_tickers(
    news_rows: list[dict],
    group_news_ids: list[int],
    result: dict,
) -> list[str]:
    rows_by_id = {
        news_row["id"]: news_row 
        for news_row in news_rows
    }
    
    input_tickers = {
        ticker
        for news_id in group_news_ids
        for ticker in rows_by_id[news_id]["symbols"] or []
    }
    
    return sorted(set(result["tickers"]) - input_tickers)


async def generate_group_development(
    group: dict,
    news_db: list,
    news_db_by_id: dict,
    semaphore: asyncio.Semaphore,
    models: list[str],
    as_of: str,
    exchange: str,
    effort: str,
    token_usage_logger: TokenUsageLogger | None = None,
) -> dict | None:
    news_ids = group["news_ids"]

    # A single article is the development, so just skips LLM
    if len(news_ids) == 1:
        news_record = news_db_by_id[news_ids[0]]

        return {
            "event": group["event"],
            "title": news_record["title"],
            "summary": news_record["body"],
            "tickers": news_record["symbols"] or [],
            "supporting_news_ids": news_ids,
        }

    async with semaphore:
        response = await invoke_structured_llm_async(
            pydantic_output=Development,
            system_prompt=get_development_system_prompt(exchange),
            user_prompt=DEVELOPMENT_USER_PROMPT,
            log_name="Group generation",
            input_data={
                "as_of": as_of,
                "articles": build_group_payload(
                    news_rows=news_db,
                    group_news_ids=news_ids
                ),
            },
            models=models,
            effort=effort,
            token_usage_logger=token_usage_logger,
        )

    if response is None:
        LOGGER.warning(
            "Group generation | no response for %s", 
            news_ids
        )
        return None

    if response["source_conflicts"]:
        LOGGER.info(
            "Group generation | %s source conflicts: %s",
            news_ids,
            response["source_conflicts"]
        )

    unknown_tickers = find_unknown_tickers(
        news_rows=news_db,
        group_news_ids=news_ids,
        result=response
    )

    if unknown_tickers:
        LOGGER.warning(
            "Group generation | %s unknown tickers: %s",
            news_ids,
            unknown_tickers
        )

    return {
        "event": group["event"],
        "title": response["title"],
        "summary": response["summary"],
        "tickers": response["tickers"],
        "supporting_news_ids": news_ids,
    }


async def run_group_generation(
    news_db: list,
    group_result: dict,
    models: list[str],
    as_of: str,
    exchange: str = "IDX",
    effort: str = "medium",
    concurrency: int = CONCURRENCY,
    token_usage_logger: TokenUsageLogger | None = None,
) -> list[dict]:
    news_db_by_id = {
        record["id"]: record
        for record in news_db
    }

    semaphore = asyncio.Semaphore(concurrency)

    developments = await asyncio.gather(
        *(
            generate_group_development(
                group=group,
                news_db=news_db,
                news_db_by_id=news_db_by_id,
                semaphore=semaphore,
                models=models,
                as_of=as_of,
                exchange=exchange,
                effort=effort,
                token_usage_logger=token_usage_logger,
            )
            for group in group_result["groups"]
        )
    )

    return [
        development 
        for development in developments 
        if development is not None
    ]
