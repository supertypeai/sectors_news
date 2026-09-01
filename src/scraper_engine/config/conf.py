from dotenv import load_dotenv

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

    OPENROUTER_API_KEY = get_required_env("OPENROUTER_API_KEY")
    GROQ_API_KEY_DEV = get_required_env("GROQ_API_KEY_DEV")
    PROXY = get_required_env('PROXY')

except ValueError as error:
    logger.critical(f"Configuration failed: {error}")
    raise


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

CRAWLER_USER_AGENT = (
    "Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible; "
    "Googlebot/2.1; +http://www.google.com/bot.html) "
    "Chrome/120.0.0.0 Safari/537.36"
)
