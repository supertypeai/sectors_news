from datetime import datetime, timedelta

from scraper_engine.llm.caller import invoke_structured_llm
from scraper_engine.llm.client import TokenUsageLogger
from scraper_engine.llm.prompt_definitions import ScoringNews, ScoringPrompts
from scraper_engine.llm.constant import MODEL_NAMES

import logging


LOGGER = logging.getLogger(__name__)


def manual_score_time(publication_timestamp: str | datetime) -> int:
    if isinstance(publication_timestamp, str):
        publication_timestamp = datetime.strptime(
            publication_timestamp, "%Y-%m-%d %H:%M:%S"
        )

    time_difference = datetime.now() - publication_timestamp

    if time_difference <= timedelta(hours=48):
        return 3
    if time_difference <= timedelta(days=7):
        return 2
    if time_difference <= timedelta(days=14):
        return 1
    return 0


def get_article_score(
    body: str,
    article_date: str,
    source_scraper: str,
    token_usage_logger: TokenUsageLogger | None = None,
) -> int | None:
    if not body or len(body.strip()) < 10:
        LOGGER.warning(
            "Article body is empty or too short for scoring. Returning 0."
        )
        return 0

    prompts = ScoringPrompts()

    if source_scraper == "sgx":
        system_prompt = prompts.get_scoring_system_prompt_sgx()
    else:
        system_prompt = prompts.get_scoring_system_prompt_idx()

    input_data = {
        "article": body,
    }

    try:
        response = invoke_structured_llm(
            pydantic_output=ScoringNews,
            system_prompt=system_prompt,
            user_prompt=prompts.get_scoring_user_prompt(),
            log_name="Scoring",
            input_data=input_data,
            models=MODEL_NAMES,
            max_retry=1,
            temperature=0.4,
            effort="high",
            token_usage_logger=token_usage_logger,
        )

        if response is None:
            LOGGER.warning("Scoring caller returned no result.")
            return None

        LOGGER.info("Reason scoring: %s", response.get("explanation"))

        final_score = response.get("score", 0) + manual_score_time(article_date)

        if 0 <= final_score <= 155:
            return final_score

        LOGGER.warning("Score out of range: %s, capping at valid range", final_score)

        return max(0, min(155, final_score))

    except Exception as error:
        LOGGER.warning("LLM failed with error: %s", error)
        LOGGER.error("All LLMs failed; returning no score")
        return None
