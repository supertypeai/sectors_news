from dotenv     import load_dotenv
from threading  import Semaphore

import os 
import asyncio
import logging

logging.basicConfig(
    # filename='app.log', # Set a file for save logger output 
    level=logging.INFO, # Set the logging level
    format='%(asctime)s [%(levelname)s] - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
    )

LOGGER = logging.getLogger(__name__)
LOGGER.info("Init Global Variable")

# load .env content
load_dotenv(override=True)

SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_URL = os.getenv("SUPABASE_URL")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
GROQ_API_KEY1 = os.getenv("GROQ_API_KEY1")
GROQ_API_KEY2 = os.getenv("GROQ_API_KEY2")
GROQ_API_KEY3 = os.getenv("GROQ_API_KEY3")

LLM_SEMAPHORE_SYNC = Semaphore(5)
LLM_SEMAPHORE = asyncio.Semaphore(5)