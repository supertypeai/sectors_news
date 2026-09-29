from scraper_engine.llm.caller import invoke_structured_llm_async
from scraper_engine.llm.client import TokenUsageLogger
from .prompts.market_brief import MarketBriefSchema, MarketBriefPrompts
from .prompts.what_to_watch import WhatToWatchPrompts, WhatToWatch
from .utils.format_records import format_records

import logging
import asyncio 


LOGGER = logging.getLogger(__name__)


async def get_market_brief(
    merged_developments: list[dict],
    exchange: str,
    brief_as_of: str,
    effort: str = "high",
    models: list[str] = [
        "deepsek-v4-flash",
        "gpt-oss-120b",
    ],
    token_usage_logger: TokenUsageLogger | None = None,
) -> dict | None:
    input_data = {
        "brief_as_of": brief_as_of,
        "developments": format_records(
            records=merged_developments,
            fields=[
                ("development_id", "Development ID"),
                ("title", "Development title"),
                ("summary", "Development summary"),
                ("tickers", "Tickers"),
                ("supporting_news_ids", "Supporting news IDs"),
            ],
        ),
    }

    brief_result = await invoke_structured_llm_async(
        pydantic_output=MarketBriefSchema,
        system_prompt=MarketBriefPrompts.get_system_prompt(exchange),
        user_prompt=MarketBriefPrompts.get_user_prompt(),
        log_name="Market pulse",
        input_data=input_data,
        models=models,
        effort=effort,
        is_log_raw_response=True,
        temperature=0.65,
        token_usage_logger=token_usage_logger,
    )

    if not brief_result:
        return None

    return brief_result


async def get_what_to_watch(
    merged_developments: list[dict],
    exchange: str,
    brief_as_of: str,
    effort: str = "high",
    models: list[str] = [
        "deepsek-v4-flash",
        "gpt-oss-120b",
    ],
    token_usage_logger: TokenUsageLogger | None = None,
) -> dict | None:
    input_data = {
        "brief_as_of": brief_as_of,
        "developments": format_records(
            records=merged_developments,
            fields=[
                ("development_id", "Development ID"),
                ("title", "Development title"),
                ("summary", "Development summary"),
                ("tickers", "Tickers"),
                ("supporting_news_ids", "Supporting news IDs"),
            ],
        ),
    }

    brief_result = await invoke_structured_llm_async(
        pydantic_output=WhatToWatch,
        system_prompt=WhatToWatchPrompts.get_system_prompt(exchange),
        user_prompt=WhatToWatchPrompts.get_user_prompt(),
        log_name="What to Watch",
        input_data=input_data,
        models=models,
        effort=effort,
        is_log_raw_response=True,
        temperature=0.3,
        token_usage_logger=token_usage_logger,
    )

    if not brief_result:
        return None

    return brief_result 


async def run_brief_generation(
    merged_developments: list[dict],
    exchange: str,
    brief_as_of: str = "",
    effort: str = "high",
    models: list[str] = [
        "glm-5.3-flash",
        "deepsek-v4-flash",
        "gpt-oss-120b",
    ],
    token_usage_logger: TokenUsageLogger | None = None,
)-> dict[str, dict | None]:
    market_brief, what_to_watch = await asyncio.gather(
        get_market_brief(
            merged_developments=merged_developments, 
            exchange=exchange,
            brief_as_of=brief_as_of,
            effort=effort, 
            models=models,
            token_usage_logger=token_usage_logger,
        ),
        get_what_to_watch(
            merged_developments=merged_developments, 
            exchange=exchange,
            brief_as_of=brief_as_of,
            effort=effort, 
            models=models,
            token_usage_logger=token_usage_logger,
        )
    )

    return {
        "market_brief": market_brief,
        "what_to_watch": what_to_watch,
    }

