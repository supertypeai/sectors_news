from langchain.chat_models import init_chat_model
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_core.outputs import ChatResult
from langchain_core.callbacks import BaseCallbackHandler

from scraper_engine.config.conf import (
    GROQ_API_KEY_DEV,
    OPENROUTER_API_KEY,
)
from scraper_engine.llm.constant import (
    ABORT_KEYWORDS,
    ABORT_STATUS_CODES,
    MODEL_CONFIG,
    ROTATE_400_KEYWORDS,
    ROTATE_KEYWORDS,
    ROTATE_STATUS_CODES,
)

import logging 


LOGGER = logging.getLogger(__name__)

# manually calculate cost for groq 
# openrouter can directly return the cost 
MODEL_TOKEN_PRICING = {
    "openai/gpt-oss-120b": {
        "input": 0.15,
        "cached_input": 0.075,
        "output": 0.60,
    },
}


class TokenUsageLogger(BaseCallbackHandler):
    def __init__(self):
        super().__init__()
        self.request_costs = []

    def on_llm_end(self, response, **kwargs):
        llm_output = response.llm_output or {}
        token_usage = llm_output.get("token_usage") or {}

        if not token_usage and response.generations:
            generation = response.generations[0][0]
            message = getattr(generation, "message", None)
            token_usage = getattr(message, "usage_metadata", None) or {}

        completion_details = token_usage.get("completion_tokens_details") or {}
        output_details = token_usage.get("output_token_details") or {}

        prompt_tokens = token_usage.get(
            "prompt_tokens",
            token_usage.get("input_tokens", 0),
        )

        completion_tokens = token_usage.get(
            "completion_tokens",
            token_usage.get("output_tokens", 0),
        )

        reasoning_tokens = completion_details.get(
            "reasoning_tokens",
            output_details.get("reasoning", 0),
        )

        total_tokens = token_usage.get("total_tokens", 0)

        generation_info = (
            response.generations[0][0].generation_info
            if response.generations
            else {}
        ) or {}

        message = response.generations[0][0].message
        model_name = llm_output.get("model_name", "unknown")
        cost = message.response_metadata.get("cost")

        if cost is None:
            pricing = MODEL_TOKEN_PRICING.get(model_name)
            prompt_tokens_details = token_usage.get("prompt_tokens_details") or {}
            cached_prompt_tokens = prompt_tokens_details.get("cached_tokens", 0)
            billable_prompt_tokens = max(
                prompt_tokens - cached_prompt_tokens,
                0,
            )

            if pricing:
                cost = (
                    billable_prompt_tokens / 1_000_000 * pricing["input"]
                    + cached_prompt_tokens / 1_000_000 * pricing["cached_input"]
                    + completion_tokens / 1_000_000 * pricing["output"]
                )

        self.request_costs.append(cost)

        if cost is not None:
            LOGGER.info("request cost: $%.8f USD", cost)
            
        LOGGER.info(
            "token usage: model=%s prompt=%d completion=%d reasoning=%d "
            "total=%d finish_reason=%s",
            model_name,
            prompt_tokens,
            completion_tokens,
            reasoning_tokens,
            total_tokens,
            generation_info.get("finish_reason", "unknown"),
        )


def extract_status_code(error: Exception) -> int | None:
    status_code = getattr(error, "status_code", None)
    if status_code is not None:
        return int(status_code)

    for token in str(error).split():
        if token.isdigit() and len(token) == 3:
            return int(token)

    return None


def classify_error(error: Exception) -> str:
    """
    Returns one of three actions:
      'rotate' -> key-level problem, try the next key
      'abort'  -> request-level or server-level problem, rotating will not help
      'raise'  -> unexpected error, propagate immediately
    """
    status_code = extract_status_code(error)
    error_message = str(error).lower()

    if status_code == 400 and any(keyword in error_message for keyword in ROTATE_400_KEYWORDS):
        return "rotate"
    
    if status_code in ROTATE_STATUS_CODES:
        return "rotate"

    if status_code in ABORT_STATUS_CODES:
        return "abort"

    if any(keyword in error_message for keyword in ROTATE_KEYWORDS):
        return "rotate"

    if any(keyword in error_message for keyword in ABORT_KEYWORDS):
        return "abort"

    return "raise"


class KeyRotatingChatModel(BaseChatModel):
    """
    Wraps a pool of LLM clients initialised with different API keys for the
    same model. On a key-level failure (429, 401, 403) it transparently
    rotates to the next available key. On request-level or server-level
    failures it raises immediately without wasting the remaining keys.
    """
    llm_pool: list[BaseChatModel]
    model_name_identifier: str

    class Config:
        arbitrary_types_allowed = True

    @property
    def _llm_type(self) -> str:
        return f"key-rotating-{self.model_name_identifier}"

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        **kwargs: any,
    ) -> ChatResult:
        last_error: Exception | None = None

        for index, llm_client in enumerate(self.llm_pool):
            try:
                return llm_client._generate(messages, stop=stop, **kwargs)
            
            except Exception as error:
                action = classify_error(error)

                if action == "rotate":
                    LOGGER.warning(
                        "Key index %s failed for '%s' "
                        "(rotating to next key). Error: %s",
                        index,
                        self.model_name_identifier,
                        error,
                    )
                    last_error = error
                    continue

                if action == "abort":
                    LOGGER.error(
                        "Non-recoverable error for '%s', "
                        "aborting key rotation. Error: %s",
                        self.model_name_identifier,
                        error,
                    )
                    raise

                raise

        raise RuntimeError(
            f"All {len(self.llm_pool)} API keys exhausted for model "
            f"'{self.model_name_identifier}'. Last error: {last_error}"
        )

    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        **kwargs: any,
    ) -> ChatResult:
        last_error: Exception | None = None

        for index, llm_client in enumerate(self.llm_pool):
            try:
                return await llm_client._agenerate(messages, stop=stop, **kwargs)
            
            except Exception as error:
                action = classify_error(error)

                if action == "rotate":
                    LOGGER.warning(
                        "Key index %s failed for '%s' "
                        "(async, rotating to next key). Error: %s",
                        index,
                        self.model_name_identifier,
                        error,
                    )
                    last_error = error
                    continue

                if action == "abort":
                    LOGGER.error(
                        "Non-recoverable error for '%s' "
                        "(async), aborting key rotation. Error: %s",
                        self.model_name_identifier,
                        error,
                    )
                    raise

                raise

        raise RuntimeError(
            f"All {len(self.llm_pool)} API keys exhausted for model "
            f"'{self.model_name_identifier}'. Last error: {last_error}"
        )
    

def get_llm(
    model_name: str,
    temperature: float = 0.5,
    effort: str = "high",
    max_retries: int = 3,
    token_usage_logger: TokenUsageLogger | None = None,
):
    config_model = MODEL_CONFIG.get(model_name)

    if config_model is None:
        available_models = ', '.join(MODEL_CONFIG.keys())
        LOGGER.error(
            "Unknown model name: %s. Available models: %s",
            model_name,
            available_models
        )
        return None

    max_tokens = config_model.get("max_tokens")
    provider = config_model.get('provider')
    
    provider_keys = {
        'groq': [GROQ_API_KEY_DEV],
        'openrouter': [OPENROUTER_API_KEY],
    }

    api_keys = [
        key
        for key in provider_keys.get(provider, [])
        if key
    ]
    
    if not api_keys:
        LOGGER.error("No valid API keys found for provider: '%s'", provider)
        return None
    
    llm_pool = []
    
    for api_key in api_keys:
        try:
            model_parameters = {
                "temperature": temperature,
                "max_retries": max_retries,
                "api_key": api_key,
                "max_tokens": max_tokens if max_tokens else 80000,
                "timeout": 180
            }

            model_id = config_model["model"]

            if provider == "openrouter":
                if not model_id.endswith(":nitro"):
                    model_id = f"{model_id}:nitro"

                model_parameters["reasoning"] = {
                    "effort": effort,
                }
                model_parameters["openrouter_provider"] = {
                    "sort": "latency",
                }
                
            elif provider == "groq" and effort != "none":
                model_parameters["reasoning_effort"] = effort

            initiate_model = init_chat_model(
                model_id,
                model_provider=provider,
                **model_parameters,
            ) 

            llm_pool.append(initiate_model)
    
        except Exception as error:
            LOGGER.error("Error initialize llm: %s", error)
            continue 
    
    if not llm_pool:
        LOGGER.error(
            "No clients could be initialized for '%s'",
            model_name,
        )
        return None

    return KeyRotatingChatModel(
        llm_pool=llm_pool,
        model_name_identifier=model_name,
        callbacks=[token_usage_logger or TokenUsageLogger()],
    )
