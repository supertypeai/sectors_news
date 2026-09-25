from scraper_engine.llm.caller import invoke_structured_llm_async
from scraper_engine.llm.client import TokenUsageLogger
from scraper_engine.llm.prompt_definitions.scoring import ScoringSchema, ScoringPrompts
from scraper_engine.llm.constant import MODEL_NAMES

import logging


LOGGER = logging.getLogger(__name__)


async def get_article_score(
    body: str,
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

    response = await invoke_structured_llm_async(
        pydantic_output=ScoringSchema,
        system_prompt=system_prompt,
        user_prompt=prompts.get_scoring_user_prompt(),
        log_name="Scoring",
        input_data=input_data,
        models=MODEL_NAMES,
        temperature=0.3,
        effort="medium",
        token_usage_logger=token_usage_logger,
    )

    if response is None:
        LOGGER.warning("Scoring caller returned no result.")
        return None

    LOGGER.info("Raw response scoring: %s", response)

    scoring_result = ScoringSchema.model_validate(response)

    final_score = scoring_result.score

    if 0 <= final_score <= 155:
        return final_score

    LOGGER.warning(
        "Score out of range: %s, capping at valid range", 
        final_score
    )

    return max(0, min(155, final_score))

