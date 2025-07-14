import logging
from dotenv import load_dotenv
import os 


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