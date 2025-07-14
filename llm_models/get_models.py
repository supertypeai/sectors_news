from langchain.chat_models  import init_chat_model
from threading              import Semaphore

from config.setup import LOGGER, OPENAI_API_KEY

import asyncio
import re 
import time
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
                    max_retries=0,
                    api_key=OPENAI_API_KEY
                ),
                init_chat_model(
                    "gpt-4o",
                    model_provider="openai",
                    temperature=0.2,
                    max_retries=0,
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


# def invoke_llm(chain, input_data):
#     """
#     Invokes the LLM chain, relying on the library's built-in retries.
#     This wrapper now manages concurrency and logs the final error if all retries fail.
#     """
#     with _LLM_SEMAPHORE_SYNC:
#         try:
#             return chain.invoke(input_data)
        
#         except (openai.APIError, openai.APITimeoutError) as error:
#             # This line only runs if the API call fails after all retries are exhausted.
#             LOGGER.error(f"LLM call failed after all retries: {error}")
            
#             # Return a default value or re-raise a custom exception for graceful failure.
#             return None


# async def invoke_llm_async(chain, input_data):
#     """
#     Asynchronously invokes the LLM chain, relying on the library's built-in retries.
#     """
#     async with _LLM_SEMAPHORE:
#         try:
#             return await chain.ainvoke(input_data)
        
#         except (openai.APIError, openai.APITimeoutError) as error:
#             LOGGER.error(f"Async LLM call failed after all retries: {error}")
#             return None


def invoke_llm(chain, input_data):
    with _LLM_SEMAPHORE_SYNC:
        while True:
            try:
                return chain.invoke(input_data)
            except openai.RateLimitError as error:
                m = re.search(r"in (\d+)ms", getattr(error, "user_message", "") or str(error))
                wait_ms = int(m.group(1)) if m else 1000
                wait_s = wait_ms / 1000.0
                buffer = 0.2  # 100 ms safety margin
                total_sleep = wait_s + buffer
                LOGGER.warning(f"429 → sleeping {total_sleep:.2f}s then retrying…")
                time.sleep(total_sleep)
            except openai.APIConnectionError as error:
                LOGGER.warning(f"Connection error → retrying in 1s: {error}")
                time.sleep(1)


async def invoke_llm_async(chain, input_data):
    async with _LLM_SEMAPHORE:
        while True:
            try:
                return await chain.ainvoke(input_data)
            except openai.RateLimitError as error:
                m = re.search(r"in (\d+)ms", getattr(error, "user_message", "") or str(error))
                wait_ms = int(m.group(1)) if m else 1000
                wait_s = wait_ms / 1000.0
                buffer = 0.2  # 100 ms safety margin
                total_sleep = wait_s + buffer
                LOGGER.warning(f"429 → sleeping {total_sleep:.2f}s then retrying…")
                await asyncio.sleep(total_sleep)
            except openai.APIConnectionError as error:
                LOGGER.warning(f"Connection error → retrying in 1s: {error}")
                await asyncio.sleep(1)
    
# Example usage:
# llm_collection = LLMCollection()
# llm_collection.add_llm("LLM1")
# llm_collection.add_llm("LLM2")
# print(llm_collection.get_llms())