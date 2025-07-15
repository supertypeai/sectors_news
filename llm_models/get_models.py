from langchain.chat_models      import init_chat_model
from langchain_core.runnables   import Runnable
from threading                  import Semaphore

from config.setup import LOGGER, OPENAI_API_KEY

import asyncio
import openai


_LLM_SEMAPHORE_SYNC = Semaphore(5)
_LLM_SEMAPHORE = asyncio.Semaphore(5)


class LLMCollection:
    """
    @brief Singleton class to manage a collection of LLM (Large Language Model) instances.
    This class ensures that only one instance of the LLMCollection exists and provides methods to add and retrieve LLM instances.
    """
    _instance = None

    def __new__(cls):
        """
        @brief Creates a new instance of LLMCollection if it doesn't already exist.
        @return The singleton instance of LLMCollection.
        """
        if cls._instance is None:
            cls._instance = super(LLMCollection, cls).__new__(cls)
            cls._instance._llms = [
                init_chat_model(
                    "gpt-4o",
                    model_provider="openai",
                    temperature=0.2,
                    max_retries=3,
                    api_key=OPENAI_API_KEY
                ),
                init_chat_model(
                    "gpt-4o",
                    model_provider="openai",
                    temperature=0.2,
                    max_retries=3,
                    api_key=OPENAI_API_KEY
                )
            ]
        return cls._instance

    def add_llm(self, llm):
        """
        @brief Adds a new LLM instance to the collection.
        @param llm The LLM instance to be added to the collection.
        """
        self._llms.append(llm)

    def get_llms(self):
        """
        @brief Retrieves the list of LLM instances in the collection.
        @return A list of LLM instances.
        """
        return self._llms


def invoke_llm(chain: Runnable, input_data: dict):
    """
    Wrapper function to invoke the LLM chain synchronously. 
    This function uses a semaphore to limit the number of concurrent LLM calls.

    Args:
        chain: The LLM chain to be invoked.
        input_data: The input data to be processed by the LLM chain.
    
    Returns:
        The result of the LLM chain invocation, or None if the API call fails after all
    """
    with _LLM_SEMAPHORE_SYNC:
        try:
            return chain.invoke(input_data)
        
        except (openai.APIError, openai.APITimeoutError) as error:
            # This line only runs if the API call fails after all retries are exhausted.
            LOGGER.error(f"LLM call failed after all retries: {error}")
            return None


async def invoke_llm_async(chain: Runnable, input_data: dict):
    """
    Wrapper function to invoke the LLM chain asynchronously.
    This function uses an asyncio semaphore to limit the number of concurrent LLM calls.

    Args:
        chain: The LLM chain to be invoked.
        input_data: The input data to be processed by the LLM chain.
    
    Returns:
        The result of the LLM chain invocation, or None if the API call fails after all
    """
    async with _LLM_SEMAPHORE:
        try:
            return await chain.ainvoke(input_data)
        
        except (openai.APIError, openai.APITimeoutError) as error:
            # This line only runs if the API call fails after all retries are exhausted.
            LOGGER.error(f"Async LLM call failed after all retries: {error}")
            return None


# Example usage:
# llm_collection = LLMCollection()
# llm_collection.add_llm("LLM1")
# llm_collection.add_llm("LLM2")
# print(llm_collection.get_llms())