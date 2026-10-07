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
    BRIGHTDATA_API_KEY = get_required_env("BRIGHTDATA_API_KEY")
    BRIGHTDATA_ZONE = get_required_env("BRIGHTDATA_ZONE")

except ValueError as error:
    logger.critical("Configuration failed: %s", error)
    raise
