from threading import Semaphore
from dotenv import load_dotenv

import asyncio
import os
import logging


logger = logging.getLogger(__name__)


load_dotenv(override=True)


def get_required_env(key: str) -> str:
    value = os.getenv(key)
    if not value:
        raise ValueError(f"Missing required environment variable: {key}")
    return value


try:
    SUPABASE_KEY = get_required_env("SUPABASE_KEY")
    SUPABASE_URL = get_required_env("SUPABASE_URL")

    OPENAI_API_KEY = get_required_env("OPENAI_API_KEY")
    GROQ_API_KEY1 = get_required_env("GROQ_API_KEY1")
    GROQ_API_KEY2 = get_required_env("GROQ_API_KEY2")
    GROQ_API_KEY3 = get_required_env("GROQ_API_KEY3")
    GROQ_API_KEY4 = get_required_env("GROQ_API_KEY4")
    GEMINI_API_KEY = get_required_env("GEMINI_API_KEY")
    
    PROXY = get_required_env('PROXY')
    
    # Semaphores
    LLM_SEMAPHORE_SYNC = Semaphore(5)
    LLM_SEMAPHORE = asyncio.Semaphore(5)

except ValueError as error:
    logger.critical(f"Configuration failed: {error}")
    raise