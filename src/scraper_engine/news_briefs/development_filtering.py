from scraper_engine.llm.caller import (
    invoke_structured_llm,
    invoke_structured_llm_async,
)
from scraper_engine.llm.client import TokenUsageLogger
from .prompts.development import DevelopmentArticles, DevelopmentPrompts
from .prompts.merge_development import (
    DevelopmentMergeResult,
    MergeDevelopmentPrompts,
    find_partition_errors,
)
from .prompts.development_topics import DevelopmentTopics, DevelopmentTopicsPrompts
from .prompts.reconcile import ReconcilePrompts, ReconciledDevelopments
from .utils.format_records import format_records

import asyncio
import logging


LOGGER = logging.getLogger(__name__)


def apply_development_merge(
    developments: list[dict],
    merge_result: dict,
) -> list[dict]:
    developments_by_id = {
        development["source_development_id"]: development
        for development in developments
    }

    grouped_development_ids = [
        development_id
        for group in merge_result["groups"]
        for development_id in group["development_ids"]
    ]

    expected_development_ids = set(developments_by_id)
    actual_development_ids = set(grouped_development_ids)

    if actual_development_ids != expected_development_ids:
        raise ValueError(
            "Merge result does not contain every input development exactly once."
        )

    if len(grouped_development_ids) != len(actual_development_ids):
        raise ValueError(
            "A development ID appears in more than one merge group."
        )

    merged_developments = []

    for group_index, group in enumerate(
        merge_result["groups"],
        start=1,
    ):
        source_development_ids = group["development_ids"]

        source_developments = [
            developments_by_id[development_id]
            for development_id in source_development_ids
        ]

        if len(source_developments) == 1:
            merged_development = source_developments[0].copy()

            merged_development.pop(
                "source_development_id",
                None,
            )

        else:
            supporting_news_ids = sorted({
                news_id
                for development in source_developments
                for news_id in development.get("supporting_news_ids") or []
            })

            tickers = sorted({
                ticker
                for development in source_developments
                for ticker in development.get("tickers") or []
            })

            merged_development = {
                "title": group["merged_title"],
                "summary": group["merged_summary"],
                "tickers": tickers,
                "supporting_news_ids": supporting_news_ids,
            }

        merged_development["development_id"] = (
            f"development_{group_index:03d}"
        )

        merged_developments.append(merged_development)

    return merged_developments


async def get_development_articles(
    articles: list[dict],
    exchange: str,
    efforts: str = "medium",
    models: list[str] = [
        "deepsek-v4-flash", 
        "gpt-oss-120b"
    ],
    token_usage_logger: TokenUsageLogger | None = None,
) -> dict: 
    system_prompt = DevelopmentPrompts.get_system_development_prompt(exchange)
    user_prompt = DevelopmentPrompts.get_user_development_prompt()

    input_data = {
        "news_articles": format_records(
            records=articles,
            fields=[
                ("id", "News ID"),
                ("title", "Title"),
                ("body", "Body"),
                ("tickers", "Tickers"),
                ("timestamp", "Article publish date"),
            ],
        )
    }
    
    response = await invoke_structured_llm_async(
        pydantic_output=DevelopmentArticles,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        log_name="Development filter",
        input_data=input_data,
        models=models,
        effort=efforts,
        token_usage_logger=token_usage_logger,
    )

    return response 


def get_merger_development(
    developments: list[dict],
    exchange: str,
    effort: str = "medium",
    models: list[str] = [
        "deepsek-v4-flash", 
        "gpt-oss-120b"
    ],
    token_usage_logger: TokenUsageLogger | None = None,
    max_partition_retry: int = 3,
)-> dict | None: 
    system_prompt = MergeDevelopmentPrompts.get_system_merge_development_prompt(exchange)
    user_prompt = MergeDevelopmentPrompts.get_user_merge_development_prompt()

    input_data = {
        "developments": format_records(
            records=developments,
            fields=[
                ("source_development_id", "Development ID"),
                ("title", "Development title"),
                ("summary", "Development summary"),
                ("tickers", "Tickers"),
                ("supporting_news_ids", "Supporting news IDs"),
            ],
        )
    }

    input_ids = {
        development["source_development_id"]
        for development in developments
    }

    # The model sometimes returns an invalid partition (an ID missing, repeated,
    # or unknown), so retry until every input ID appears exactly once
    for attempt in range(1, max_partition_retry + 1):
        response = invoke_structured_llm(
            pydantic_output=DevelopmentMergeResult,
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            log_name="Merged development",
            input_data=input_data,
            models=models,
            effort=effort,
            token_usage_logger=token_usage_logger,
        )

        if response is None:
            return None

        partition_errors = find_partition_errors(
            result=DevelopmentMergeResult.model_validate(response),
            input_ids=input_ids,
        )

        if not any(partition_errors.values()):
            return response

        LOGGER.warning(
            "Merged development | invalid partition on attempt %d/%d | %s",
            attempt,
            max_partition_retry,
            {key: sorted(value) for key, value in partition_errors.items() if value},
        )

    return None


async def process_development_batch(
    batch_articles: list[dict],
    exchange: str,
    batch_number: int,
    total_batches: int,
    models: list[str],
    effort: str,
    semaphore: asyncio.Semaphore,
    token_usage_logger: TokenUsageLogger | None,
):
    async with semaphore:
        LOGGER.info(
            "Processing development batch: %d/%d | articles: %d",
            batch_number,
            total_batches,
            len(batch_articles),
        )

        result = await get_development_articles(
            articles=batch_articles,
            exchange=exchange,
            models=models,
            efforts=effort,
            token_usage_logger=token_usage_logger,
        )

        await asyncio.sleep(1)

        return result


def process_development_to_topic(
    merged_developments: list[dict],
    exchange: str,
    models: list[str] = [
        "deepsek-v4-flash", 
        "gpt-oss-120b"
    ], 
    effort: str = "medium",  
    token_usage_logger: TokenUsageLogger | None = None,
) -> dict: 
    input_data = {
        "developments": format_records(
            records=merged_developments,
            fields=[
                ("title", "Development title"),
                ("summary", "Development summary"),
            ],
        )
    }

    response = invoke_structured_llm(
        pydantic_output=DevelopmentTopics,
        system_prompt=DevelopmentTopicsPrompts.get_system_development_topics(exchange),
        user_prompt=DevelopmentTopicsPrompts.get_user_development_topics(),
        log_name="Development topic",
        input_data=input_data,
        models=models,
        effort=effort,
        is_log_raw_response=True,
        token_usage_logger=token_usage_logger,
    ) 

    return response


def run_development_reconcile(  
    current_developments: list[dict],
    topic_developments: list[str],
    exchange: str,
    models: list[str] = [
        "deepsek-v4-flash", 
        "gpt-oss-120b"
    ], 
    effort: str = "medium",      
    token_usage_logger: TokenUsageLogger | None = None,
) -> dict:
    input_data = {
        "development_topics": format_records(
            records=topic_developments, 
            fields=[
                ("topic", "Topic"),
                ("known_state", "Known state"),
            ]
        ), 
        "current_developments": format_records(
            records=current_developments, 
            fields=[
                ("title", "Title"),
                ("summary", "Summary"),
                ("development_id", "Development ID"),
            ],
        )
    }

    response = invoke_structured_llm(
        pydantic_output=ReconciledDevelopments,
        system_prompt=ReconcilePrompts.get_system_prompt(exchange),
        user_prompt=ReconcilePrompts.get_user_prompt(),
        log_name="Reconcile developments",
        input_data=input_data,
        models=models,
        effort=effort,
        is_log_raw_response=False,
        token_usage_logger=token_usage_logger,
    ) 

    return response


async def run_development_generation(
    articles: list[dict],
    exchange: str,
    models: list[str] = [
        "deepsek-v4-flash", 
        "gpt-oss-120b"
    ], 
    effort_chunk: str = "medium", 
    effort_merger: str = "high",
    batch: int = 30,
    concurrency: int = 4,
    token_usage_logger: TokenUsageLogger | None = None,
) -> dict:  
    article_batches = [
        articles[index:index + batch]
        for index in range(0, len(articles), batch)
    ]
    semaphore = asyncio.Semaphore(concurrency)

    batch_results = await asyncio.gather(
        *(
            process_development_batch(
                batch_articles=batch_articles,
                exchange=exchange,
                batch_number=batch_number,
                total_batches=len(article_batches),
                models=models,
                effort=effort_chunk,
                semaphore=semaphore,
                token_usage_logger=token_usage_logger,
            )
            for batch_number, batch_articles in enumerate(
                article_batches,
                start=1,
            )
        )
    )

    final_developments = []

    for result in batch_results:
        if result:
            final_developments.extend(result.get("developments") or [])

    identified_developments = [
        {
            **development,
            "source_development_id": f"dev_{development_index:03d}",
        }
        for development_index, development in enumerate(
            final_developments,
            start=1,
        )
    ]
    
    merge_result = get_merger_development(
        developments=identified_developments,
        exchange=exchange,
        models=models,
        effort=effort_merger,
        token_usage_logger=token_usage_logger,
    )

    if merge_result is None:
        raise RuntimeError("Development merge failed after all retries.")

    merged_developments = apply_development_merge(
        developments=identified_developments,
        merge_result=merge_result,
    )

    return {
        "developments": merged_developments
    }
