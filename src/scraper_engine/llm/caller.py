import asyncio
import logging
import time

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.prompts import ChatPromptTemplate
from pydantic import BaseModel, ValidationError

from .client import TokenUsageLogger, get_llm


LOGGER = logging.getLogger(__name__)

DEFAULT_MODELS = (
    "gpt-oss-120b",
    "deepsek-v4-flash",
    "glm-5.3-flash",
    "nvidia-nemotron-3-ultra",
)
RETRY_DELAY_SECONDS = 2.5


def _prepare_structured_request(
    pydantic_output: type[BaseModel],
    system_prompt: str,
    user_prompt: str,
    input_data: dict[str, object],
) -> tuple[ChatPromptTemplate, JsonOutputParser, dict[str, object]]:
    parser = JsonOutputParser(pydantic_object=pydantic_output)
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("user", user_prompt),
    ])
    request_data = {
        **input_data,
        "format_instructions": parser.get_format_instructions(),
    }

    return prompt, parser, request_data


def _get_llm_for_attempt(
    model: str,
    temperature: float,
    effort: str,
    log_name: str,
    attempt: int,
    max_retry: int,
    token_usage_logger: TokenUsageLogger | None,
) -> BaseChatModel | None:
    llm = get_llm(
        model,
        temperature=temperature,
        effort=effort,
        token_usage_logger=token_usage_logger,
    )

    if llm is not None:
        LOGGER.info(
            "[LLM Caller][%s] model used %s (attempt %d/%d)",
            log_name,
            model,
            attempt,
            max_retry,
        )

    return llm


def _validate_extraction(
    extraction: object,
    pydantic_output: type[BaseModel],
    model: str,
) -> dict | None:
    if isinstance(extraction, list):
        extraction = next(
            (
                item
                for item in extraction
                if isinstance(item, dict)
            ),
            None,
        )

    if not isinstance(extraction, dict):
        LOGGER.warning(
            "[fallback] %s returned non-object extraction, skipping",
            model,
        )
        return None

    try:
        validated_extraction = pydantic_output.model_validate(extraction)

    except ValidationError as validation_error:
        LOGGER.warning(
            "[fallback] %s returned invalid structured data: %s",
            model,
            validation_error,
        )
        return None

    return validated_extraction.model_dump()


def invoke_structured_llm(
    pydantic_output: type[BaseModel],
    system_prompt: str,
    user_prompt: str,
    log_name: str,
    input_data: dict[str, object],
    models: list[str] | None = None,
    max_retry: int = 3,
    temperature: float = 0.3,
    effort: str = "low",
    is_log_raw_response: bool = False,
    token_usage_logger: TokenUsageLogger | None = None,
) -> dict | None:
    if token_usage_logger is None:
        token_usage_logger = TokenUsageLogger()

    prompt, parser, request_data = _prepare_structured_request(
        pydantic_output=pydantic_output,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        input_data=input_data,
    )

    model_names = DEFAULT_MODELS if models is None else models

    for model in model_names:
        for attempt in range(1, max_retry + 1):
            try:
                llm = _get_llm_for_attempt(
                    model=model,
                    temperature=temperature,
                    effort=effort,
                    log_name=log_name,
                    attempt=attempt,
                    max_retry=max_retry,
                    token_usage_logger=token_usage_logger,
                )

                if llm is None:
                    continue

                extraction = (prompt | llm | parser).invoke(request_data)

                if is_log_raw_response:
                    LOGGER.info(
                        "[LLM Caller] raw extraction: %s",
                        extraction,
                    )

                validated_extraction = _validate_extraction(
                    extraction=extraction,
                    pydantic_output=pydantic_output,
                    model=model,
                )
                if validated_extraction is not None:
                    return validated_extraction

            except Exception as error:
                LOGGER.warning(
                    "[fallback] model %s failed: %s",
                    model,
                    error,
                )

            if attempt < max_retry:
                time.sleep(RETRY_DELAY_SECONDS)

    return None


async def invoke_structured_llm_async(
    pydantic_output: type[BaseModel],
    system_prompt: str,
    user_prompt: str,
    log_name: str,
    input_data: dict[str, object],
    models: list[str] | None = None,
    max_retry: int = 3,
    temperature: float = 0.3,
    effort: str = "low",
    is_log_raw_response: bool = False,
    token_usage_logger: TokenUsageLogger | None = None,
) -> dict | None:
    if token_usage_logger is None:
        token_usage_logger = TokenUsageLogger()

    prompt, parser, request_data = _prepare_structured_request(
        pydantic_output=pydantic_output,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        input_data=input_data,
    )
    model_names = DEFAULT_MODELS if models is None else models

    for model in model_names:
        for attempt in range(1, max_retry + 1):
            try:
                llm = _get_llm_for_attempt(
                    model=model,
                    temperature=temperature,
                    effort=effort,
                    log_name=log_name,
                    attempt=attempt,
                    max_retry=max_retry,
                    token_usage_logger=token_usage_logger,
                )

                if llm is None:
                    continue

                extraction = await asyncio.wait_for(
                    (prompt | llm | parser).ainvoke(request_data),
                    timeout=180,
                )

                if is_log_raw_response:
                    LOGGER.info(
                        "[LLM Caller] raw extraction: %s",
                        extraction,
                    )

                validated_extraction = _validate_extraction(
                    extraction=extraction,
                    pydantic_output=pydantic_output,
                    model=model,
                )
                if validated_extraction is not None:
                    return validated_extraction

            except asyncio.TimeoutError:
                LOGGER.warning(
                    "[fallback] model %s timed out after 180 seconds",
                    model,
                )
                break

            except Exception as error:
                LOGGER.warning(
                    "[fallback] %s failed: %s",
                    model,
                    error,
                )

            if attempt < max_retry:
                await asyncio.sleep(RETRY_DELAY_SECONDS)

    return None
