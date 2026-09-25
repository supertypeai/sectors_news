from scraper_engine.database.metadata import (
    load_subsector_data_idx as load_subsector_data_idx_from_metadata,
    load_subsector_data_sgx as load_subsector_data_sgx_from_metadata,
    load_tag_data as load_tag_data_from_metadata,
)
from scraper_engine.llm.caller import invoke_structured_llm_async
from scraper_engine.llm.client import TokenUsageLogger
from scraper_engine.llm.constant import MODEL_NAMES
from scraper_engine.llm.prompt_definitions.classification import (
    ClassifierPrompts, 
    ClassificationSchema, 
    SubsectorClassification
)

import logging


LOGGER = logging.getLogger(__name__)


def validate_tag_response(tags: list[dict], response: dict) -> dict:
    result_output = response.get("tags", [])

    valid_tag_names = [
        tag.get("name") 
        for tag in tags
    ]

    seen_tags = set()
    checked_tags = []

    for tag in result_output:
        if tag in valid_tag_names and tag not in seen_tags:
            seen_tags.add(tag)
            checked_tags.append(tag)

    # override response 
    response["tags"] = checked_tags
    return response


async def classify_data(
    body: str,
    category: str,
    source_scraper: str,
    title: str,
    effort: str = "low", 
    models: list[str] = MODEL_NAMES,
    token_usage_logger: TokenUsageLogger | None = None,
) -> list[str] | str | dict[str, int | None] | None:
    prompts = ClassifierPrompts()

    prompt_methods = {
        "classification": {
            "system_prompt": prompts.get_system_classification_prompt(),
            "user_prompt": prompts.get_user_classification_prompt(),
        },
        "subsectors": {
            "system_prompt": prompts.get_system_subsectors_prompt(),
            "user_prompt": prompts.get_user_subsectors_prompt(),
        },       
    }

    tags, tags_string = load_tag_data_from_metadata()

    if source_scraper == "sgx":
        subsectors = load_subsector_data_sgx_from_metadata()
    elif source_scraper == "idx":
        subsectors, _ = load_subsector_data_idx_from_metadata()

    model_mapping = {
        "classification": ClassificationSchema,
        "subsectors": SubsectorClassification,
    }

    system_prompt = prompt_methods[category]["system_prompt"]
    user_prompt = prompt_methods[category]["user_prompt"]

    if category == "classification":
        input_data = {
            "market": source_scraper,
            "tags": tags_string,
            "title": title,
            "body": body
        }
    elif category == "subsectors":
        input_data = {
            "title": title,
            "body": body,
            "subsectors": subsectors,
        }

    try:
        response = await invoke_structured_llm_async(
            pydantic_output=model_mapping[category],
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            log_name=f"{category}",
            input_data=input_data,
            models=models,
            temperature=0.4,
            effort=effort,
            token_usage_logger=token_usage_logger,
        )

        if response is None:
            LOGGER.error("All LLMs failed for category %s.", category)
            return None

        if category == "classification":
            response = validate_tag_response(
                tags=tags, 
                response=response
            )

            return response

        elif category == "subsectors":
            reasoning = response.get("explanation")

            LOGGER.info("Reasoning subsector: %s", reasoning)
            return response

    except Exception as error:
        LOGGER.error(
            "[ERROR] LLM failed classified with error: %s",
            error,
            exc_info=True,
        )
        return None

