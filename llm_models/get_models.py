from langchain.chat_models      import init_chat_model
from langchain_core.runnables   import Runnable

from config.setup import (GROQ_API_KEY1, GROQ_API_KEY2, GROQ_API_KEY3, GROQ_API_KEY4,
                          OPENAI_API_KEY, GEMINI_API_KEY, LLM_SEMAPHORE, LLM_SEMAPHORE_SYNC)

import groq 
import openai


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

            model_providers = {
                "openai/gpt-oss-120b": "groq",
                "gemini-2.5-flash": "google_genai",
                "openai/gpt-oss-20b": "groq",
                "qwen/qwen3-32b": "groq",
                "deepseek-r1-distill-llama-70b": "groq",
                "llama-3.3-70b-versatile": "groq",
                "gpt-4.1-mini": "openai",
            }

            groq_api_keys = [GROQ_API_KEY1, GROQ_API_KEY2,
                             GROQ_API_KEY3, GROQ_API_KEY4]

            llms= []
            for model, provider in model_providers.items():
                if provider == 'groq':
                    for groq_key in groq_api_keys:
                        llms.append(
                            init_chat_model(
                                model,
                                model_provider=provider,
                                temperature=0.15,
                                max_retries=3,
                                api_key=groq_key,
                            )
                        )
                
                elif provider == 'openai':
                     llms.append(
                        init_chat_model(
                            model,
                            model_provider=provider,
                            temperature=0.15,
                            max_retries=3,
                            api_key=OPENAI_API_KEY,
                        )
                    )
                    
                elif provider == 'google_genai':
                     llms.append(
                        init_chat_model(
                            model,
                            model_provider=provider,
                            temperature=0.3,
                            max_retries=3,
                            api_key=GEMINI_API_KEY,
                        )
                    )


            cls._instance._llms = llms 

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
    with LLM_SEMAPHORE_SYNC:
        try:
            return chain.invoke(input_data)
        
        except (groq.APIError, groq.APITimeoutError, openai.APIError, openai.APITimeoutError) as error:
            raise 


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
    async with LLM_SEMAPHORE:
        try:
            return await chain.ainvoke(input_data)
        
        except (groq.APIError, groq.APITimeoutError, openai.APIError, openai.APITimeoutError) as error:
            raise


# Example usage:
# llm_collection = LLMCollection()
# llm_collection.add_llm("LLM1")
# llm_collection.add_llm("LLM2")
# print(llm_collection.get_llms())