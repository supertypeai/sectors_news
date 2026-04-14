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
    GROQ_API_KEY5 = get_required_env("GROQ_API_KEY5")
    GROQ_API_KEY_DEV = get_required_env("GROQ_API_KEY_DEV")

    GEMINI_API_KEY = get_required_env("GEMINI_API_KEY")
    GEMINI_API_KEY2 = get_required_env("GEMINI_API_KEY2")
    GEMINI_API_KEY3 = get_required_env('GEMINI_API_KEY3')
    

    PROXY = get_required_env('PROXY')

    # Semaphores
    LLM_SEMAPHORE_SYNC = Semaphore(5)
    LLM_SEMAPHORE = asyncio.Semaphore(5)

except ValueError as error:
    logger.critical(f"Configuration failed: {error}")
    raise

MODEL_NAMES = ['gpt-oss-20b', 'gpt-oss-120b', 'gemini-2.5-flash', 'llama-3.3-70b', 'kimi-k2']

MODEL_CONFIG = { 
    'kimi-k2': {
        'model': 'moonshotai/kimi-k2-instruct-0905',
        'provider': 'groq', 
        # 'key': GROQ_API_KEY
    },
    'gpt-oss-120b': {
        'model': 'openai/gpt-oss-120b',
        'provider': 'groq', 
        # 'key': GROQ_API_KEY
    },
    'gpt-oss-20b': {
        'model': 'openai/gpt-oss-20b',
        'provider': 'groq', 
        # 'key': GROQ_API_KEY
    },
    'gemini-2.5-flash': {
        'model': 'gemini-2.5-flash',
        'provider': 'google-genai', 
        # 'key': GEMINI_API_KEY
    },
    'llama-3.3-70b': {
        'model': 'llama-3.3-70b-versatile',
        'provider': 'groq', 
        # 'key': GROQ_API_KEY
    }
}

ROTATE_STATUS_CODES = {401, 403, 429, 413}
ABORT_STATUS_CODES = {400, 422, 500, 502, 503, 504}

ROTATE_KEYWORDS = (
    "rate limit", "too many requests", "authentication", "invalid api key", 
    "request too large"
)
ROTATE_400_KEYWORDS = ("organization_restricted",)
ABORT_KEYWORDS = (
    "context length", "max token", "internal server",
    "bad gateway", "service unavailable",
)


USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "*/*",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0",
    "x-test": "true",
}

HEADERS_SCRAPER = {
    'User-Agent': USER_AGENT,
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
}