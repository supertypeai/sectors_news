from datetime import time
from pathlib import Path
from zoneinfo import ZoneInfo


# Each session closes shortly after the market's pre-open/close scrape lands
# the Dagu briefs schedule fires at these same local times
MARKETS = {
    "idx": {
        "exchange": "IDX",
        "table": "idx_news",
        "timezone": ZoneInfo("Asia/Jakarta"),
        "sessions": [
            ("pre_open", time(8, 35)),
            ("post_close", time(16, 35)),
        ],
    },
    "sgx": {
        "exchange": "SGX",
        "table": "sgx_news",
        "timezone": ZoneInfo("Asia/Singapore"),
        "sessions": [
            ("pre_open", time(8, 20)),
            ("post_close", time(17, 20)),
        ],
    },
}

BRIEFS_TABLE = "news_briefs"
STATE_DIR = Path("data/briefs_result")
BACKFILL_OUTPUT_DIR = Path("src/scraper_engine/brief_preprocessing/data")
PREVIOUS_BRIEFS_FOR_RECONCILE = 2
