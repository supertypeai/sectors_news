from scraper_engine.llm.caller import invoke_structured_llm
from scraper_engine.llm.client import TokenUsageLogger
from .prompts.policy_filtering import PolicyFilterPrompts, PolicyFilterSchema
from .utils.format_records import format_records

import logging


LOGGER = logging.getLogger(__name__)


def run_policy_news_filtering(
    articles: list[dict],
    exchange: str,
    models: list[str],
    effort: str,
    brief_as_of: str,
    token_usage_logger: TokenUsageLogger | None = None,
) -> dict:
    tags_to_filter = [
        "Government Policy",
        "Central Bank",
        "Politics & Regulation",
        "Risk & Compliance",
    ]

    policy_articles = []

    for record in articles:
        tags = record.get("tags") or []

        if not any(tag in tags_to_filter for tag in tags):
            continue

        if record.get("id") is None:
            continue

        policy_articles.append(record)

    LOGGER.info(
        "Policy filter candidates: %d/%d articles",
        len(policy_articles),
        len(articles),
    )

    if not policy_articles:
        return {
            "explanation": "",
            "policies": [],
        }

    input_data = {
        "brief_as_of": brief_as_of,
        "news_articles": format_records(
            records=policy_articles,
            fields=[
                ("id", "Article ID"),
                ("timestamp", "Article timestamp"),
                ("title", "Title"),
                ("body", "Article body"),
                ("tickers", "Tickers"),
            ],
        ),
    }

    response = invoke_structured_llm(
        pydantic_output=PolicyFilterSchema,
        system_prompt=PolicyFilterPrompts.get_system_prompt(exchange),
        user_prompt=PolicyFilterPrompts.get_user_prompt(),
        log_name="Policy filter",
        input_data=input_data,
        models=models,
        effort=effort,
        token_usage_logger=token_usage_logger,
    )

    if not response:
        return {
            "explanation": "",
            "policies": [],
        }

    articles_by_id = {
        record["id"]: record
        for record in policy_articles
    }

    selected_policies = []
    seen_article_ids = set()

    for selected_policy in response["selected_policies"][:3]:
        selected_id = selected_policy["id"]
        if selected_id in seen_article_ids:
            continue

        record = articles_by_id.get(selected_id)

        if record is None:
            continue

        seen_article_ids.add(selected_id)

        selected_title = selected_policy["title"].strip()
        
        selected_policies.append({
            "id": record["id"],
            "created_at": record.get("created_at"),
            "timestamp": record.get("timestamp"),
            "title": selected_title or record.get("title"),
            "symbols": record.get("tickers") or record.get("symbols") or [],
            "thumbnail": record.get("thumbnail"),
            "source": record.get("source"),
            "tags": record.get("tags") or [],
        })

    return {
        "explanation": response["explanation"],
        "policies": selected_policies,
    }
