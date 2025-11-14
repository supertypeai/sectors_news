from dotenv     import load_dotenv
from threading  import Semaphore

import os 
import asyncio
import logging


LOGGER = logging.getLogger(__name__)
LOGGER.setLevel(logging.INFO)

# Console handler only
console_handler = logging.StreamHandler()
console_handler.setLevel(logging.INFO)

formatter = logging.Formatter(
    '%(asctime)s [%(levelname)s] - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
console_handler.setFormatter(formatter)

LOGGER.addHandler(console_handler)

LOGGER.info("Init Global Variable")

# load .env content
load_dotenv(override=True)

SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GROQ_API_KEY1 = os.getenv("GROQ_API_KEY1")
GROQ_API_KEY2 = os.getenv("GROQ_API_KEY2")
GROQ_API_KEY3 = os.getenv("GROQ_API_KEY3")
GROQ_API_KEY4 = os.getenv("GROQ_API_KEY4")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

LLM_SEMAPHORE_SYNC = Semaphore(5)
LLM_SEMAPHORE = asyncio.Semaphore(5)