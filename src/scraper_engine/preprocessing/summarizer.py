from goose3 import Goose

from scraper_engine.llm.caller import invoke_structured_llm_async
from scraper_engine.llm.client import TokenUsageLogger
from scraper_engine.llm.prompt_definitions.summarization import SummarizationPrompts, SummaryNews
from scraper_engine.config.conf import USER_AGENT
from scraper_engine.llm.constant import MODEL_NAMES
from .article_fetcher import extract_table_content
from scraper_engine.utils.article_helpers import (
    basic_cleaning_body,
    clean_apostrophe_case,
    normalize_company_abbreviations,
    normalize_dot_case,
)

import re
import cloudscraper
import logging


LOGGER = logging.getLogger(__name__)


def cleaning_summary(raw_body: str):
    cleaned_body = basic_cleaning_body(raw_body)
    cleaned_body = clean_apostrophe_case(cleaned_body)
    cleaned_body = normalize_company_abbreviations(cleaned_body)
    cleaned_body = normalize_dot_case(cleaned_body)

    return cleaned_body


async def summarize_article(
    title: str,
    body: str,
    source_scraper: str = "idx",
    models: list[str] = MODEL_NAMES,
    token_usage_logger: TokenUsageLogger | None = None,
) -> dict[str]:
    prompts = SummarizationPrompts()

    if source_scraper == "idx":
        system_prompt = prompts.get_system_prompt_idx()
        user_prompt = prompts.get_user_prompt_idx()

    elif source_scraper == "sgx": 
        system_prompt = prompts.get_system_prompt_sgx()
        user_prompt = prompts.get_user_prompt_sgx()

    input_data = {
        "title": title,
        "article": body,
    }

    summary_result = await invoke_structured_llm_async(
        pydantic_output=SummaryNews,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        log_name="Summarization",
        input_data=input_data,
        models=models,
        temperature=0.35,
        effort="medium",
        token_usage_logger=token_usage_logger,
    )

    if summary_result is None:
        LOGGER.warning("Summarization caller returned no result.")
        return None

    return summary_result


async def summarize_news(
    url: str,
    news_text: str,
    title: str,
    source_scraper: str = "idx",
    models: list[str] = MODEL_NAMES,
    token_usage_logger: TokenUsageLogger | None = None,
) -> tuple[str, str] | None:
    try:
        if len(news_text) <= 100:
            LOGGER.warning(
                "Article text too short (%s chars) for %s, retrying with cloudscraper.",
                len(news_text),
                url,
            )
            scraper = cloudscraper.create_scraper()
            goose_extractor = Goose(
                {"browser_user_agent": USER_AGENT, "http_session": scraper}
            )
            article = goose_extractor.extract(url=url)

            if not article.cleaned_text or len(article.cleaned_text) <= 100:
                LOGGER.error(
                    "Cloudscraper also returned insufficient content for %s.", 
                    url
                )
                return None

            news_text = article.cleaned_text

        news_text = re.sub(r"\s+", " ", news_text)

        if "businesstimes" in url:
            table_text = extract_table_content(url)
            if table_text:
                news_text = news_text + "\n" + table_text

        LOGGER.info("Article content preview: %s", news_text[:550])

        response = await summarize_article(
            title=title, 
            body=news_text, 
            source_scraper=source_scraper,
            models=models,
            token_usage_logger=token_usage_logger,
        )

        raw_body = response.get("body")
        cleaned_body = cleaning_summary(raw_body)

        raw_title = response.get("title")
        cleaned_title = normalize_company_abbreviations(raw_title)

        return cleaned_title, cleaned_body

    except Exception as error:
        LOGGER.error(
            "Unexpected error in summarize_news for %s: %s",
            url,
            error,
            exc_info=True,
        )
        return None
