from pathlib import Path

import json
import logging


LOGGER = logging.getLogger(__name__)

PREVIOUS_RUN_FILE = Path("data") / "idx" / "pipeline_yesterday.json"


def load_previous_run_articles(path: Path = PREVIOUS_RUN_FILE) -> dict[str, dict]:
    try:
        articles = json.loads(path.read_text(encoding="utf-8"))

    except FileNotFoundError:
        return {}

    except Exception as error:
        LOGGER.warning("Failed to read previous run file %s: %s", path, error)
        return {}

    if not isinstance(articles, list):
        return {}

    return {
        article["source"]: article
        for article in articles
        if isinstance(article, dict)
        and article.get("source")
        and article.get("timestamp")
    }
