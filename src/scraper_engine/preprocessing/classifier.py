import asyncio
import logging

from scraper_engine.database.metadata import (
    load_subsector_data_idx as load_subsector_data_idx_from_metadata,
    load_subsector_data_sgx as load_subsector_data_sgx_from_metadata,
    load_tag_data as load_tag_data_from_metadata,
)
from scraper_engine.llm.caller import invoke_structured_llm_async
from scraper_engine.llm.client import TokenUsageLogger
from scraper_engine.llm.constant import MODEL_NAMES
from scraper_engine.llm.prompt_definitions import (
    ClassifierPrompts,
    DimensionClassification,
    SentimentClassification,
    SubsectorClassification,
    TagsClassification,
)


LOGGER = logging.getLogger(__name__)


async def classify_data(
    body: str,
    category: str,
    source_scraper: str,
    title: str,
    token_usage_logger: TokenUsageLogger | None = None,
) -> list[str] | str | dict[str, int | None] | None:
    prompts = ClassifierPrompts()

    prompt_methods = {
        "tags": {
            "system_prompt": prompts.get_system_tags_prompt(),
            "user_prompt": prompts.get_user_tags_prompt(),
        },
        "subsectors": {
            "system_prompt": prompts.get_system_subsectors_prompt(),
            "user_prompt": prompts.get_user_subsectors_prompt(),
        },
        "sentiment": {
            "system_prompt": prompts.get_sentiment_system_prompt(
                market=source_scraper
            ),
            "user_prompt": prompts.get_sentiment_user_prompt(),
        },
        "dimension": {
            "system_prompt": prompts.get_system_dimension_prompt(),
            "user_prompt": prompts.get_user_dimension_prompt(),
        },
    }

    tags, tags_string = load_tag_data_from_metadata()

    if source_scraper == "sgx":
        subsectors = load_subsector_data_sgx_from_metadata()
    elif source_scraper == "idx":
        subsectors, _ = load_subsector_data_idx_from_metadata()

    model_mapping = {
        "tags": TagsClassification,
        "subsectors": SubsectorClassification,
        "sentiment": SentimentClassification,
        "dimension": DimensionClassification,
    }

    system_prompt = prompt_methods[category]["system_prompt"]
    user_prompt = prompt_methods[category]["user_prompt"]

    if category == "tags":
        input_data = {
            "title": title,
            "body": body,
            "tags": tags_string,
        }
    elif category == "subsectors":
        input_data = {
            "title": title,
            "body": body,
            "subsectors": subsectors,
        }
    else:
        input_data = {
            "title": title,
            "body": body,
        }

    try:
        result = await invoke_structured_llm_async(
            pydantic_output=model_mapping[category],
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            log_name="Classification",
            input_data=input_data,
            models=MODEL_NAMES,
            temperature=0.4,
            effort="medium",
            token_usage_logger=token_usage_logger,
        )

        if result is None:
            LOGGER.error("All LLMs failed for category %s.", category)
            return None

        if category == "tags":
            result_output = result.get("tags", [])
            reason = result.get("explanation")

            LOGGER.info("Reason tags: %s", reason)

            valid_tag_names = [tag.get("name") for tag in tags]
            seen_tags = set()
            checked_tags = []

            for tag in result_output:
                if tag in valid_tag_names and tag not in seen_tags:
                    seen_tags.add(tag)
                    checked_tags.append(tag)

            return checked_tags

        if category == "subsectors":
            sub_sector = result.get("subsector", [])
            reasoning = result.get("explanation")

            if len(sub_sector) >= 10:
                return None

            LOGGER.info("Reasoning subsector: %s", reasoning)

            return sub_sector

        if category == "sentiment":
            LOGGER.info("Reason sentiment: %s", result.get("explanation"))
            return result.get("sentiment", "Not Applicable")

        result.pop("reasoning", None)
        return result

    except Exception as error:
        LOGGER.error(
            "[ERROR] LLM failed classified with error: %s",
            error,
            exc_info=True,
        )
        return None


async def classify_article(
    title: str,
    body: str,
    source_scraper: str,
    token_usage_logger: TokenUsageLogger | None = None,
) -> tuple[list[str], str, dict[str, int | None]] | None:
    tags, sentiment, dimension = await asyncio.gather(
        classify_data(
            body,
            "tags",
            source_scraper,
            title,
            token_usage_logger,
        ),
        classify_data(
            body,
            "sentiment",
            source_scraper,
            title,
            token_usage_logger,
        ),
        classify_data(
            body,
            "dimension",
            source_scraper,
            title,
            token_usage_logger,
        ),
    )

    results = [tags, sentiment, dimension]

    if any(
        isinstance(result, Exception) or result is None
        for result in results
    ):
        LOGGER.error(
            "One or more classification steps failed. "
            "Failing entire article classification."
        )
        return None

    return tags, sentiment, dimension
