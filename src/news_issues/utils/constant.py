from datetime import time
from enum import Enum


CONCURRENCY = 5

MARKET_TIME_ZONES = {
    "IDX": "Asia/Jakarta",
    "SGX": "Asia/Singapore",
}

NEWS_TABLES = {
    "IDX": "idx_news",
    "SGX": "sgx_news",
}

# IDX publishes a daily issue, SGX a weekly one cut off on Friday
ISSUE_WINDOW_DAYS = {
    "IDX": 1,
    "SGX": 7,
}

# Local cutoff each issue window ends at, 5 minutes before the final run.
# IDX's falls after the 20:15 WIB scrape so post-close filings stay in the day's issue
ISSUE_CUTOFF_TIMES = {
    "IDX": time(20, 50),
    "SGX": time(17, 20),
}

DAILY_DATA_TABLES = {
    "IDX": "idx_daily_data",
    "SGX": "sgx_daily_data",
}

DEFAULT_MODELS = [
    "gpt-6-luna",
    "glm-5.3-flash",
]

class Exchange(str, Enum):
    IDX = "IDX"
    SGX = "SGX"
