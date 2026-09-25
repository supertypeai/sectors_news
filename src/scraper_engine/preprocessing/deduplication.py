from scraper_engine.llm.caller import invoke_structured_llm
from scraper_engine.llm.prompt_definitions.deduplication import (
    SYSTEM_PROMPT, 
    USER_PROMPT,
    DeduplicationSchema
)
from scraper_engine.llm.constant import MODEL_NAMES
from scraper_engine.llm.client import TokenUsageLogger


def format_articles_for_dedup(
    articles: list[dict]
) -> str:
    parts = []

    for index, article in enumerate(articles):
        parts.append(
            f"""
                ARTICLE {index}
                Title: {article["title"]}
                Published: {article["timestamp"]}
                Source: {article["source"]}
                Summary:
                {article["body"]}
            """.strip()
        )

    return "\n\n".join(parts)


def apply_deduplication(
    articles: list,
    dedup_result: dict,
) -> list:
    groups = dedup_result.get("groups", [])

    duplicate_indexes = {
        duplicate_index
        for group in groups
        for duplicate_index in group.get("duplicate_indexes", [])
    }

    return [
        article
        for index, article in enumerate(articles)
        if index not in duplicate_indexes
    ]


def run_dedup_articles(
    survived_articles: list[dict],  
    token_usage_logger: TokenUsageLogger,
    effort: str = "high", 
    models: list[str] = MODEL_NAMES, 
    temperature: float = 0.3
) -> list[dict]:  
    if len(survived_articles) <= 1:
        return survived_articles
     
    formated_articles = format_articles_for_dedup(
        articles=survived_articles
    )
    
    input_data = {
        "articles": formated_articles
    }

    response = invoke_structured_llm(
        pydantic_output=DeduplicationSchema,
        system_prompt=SYSTEM_PROMPT,
        user_prompt=USER_PROMPT,
        log_name="Deduplication",
        input_data=input_data,
        models=models,
        temperature=temperature,
        effort=effort,
        is_log_raw_response=True,
        token_usage_logger=token_usage_logger,
    )   

    return apply_deduplication(
        articles=survived_articles,
        dedup_result=response,
    )

