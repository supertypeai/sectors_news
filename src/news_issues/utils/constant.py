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
