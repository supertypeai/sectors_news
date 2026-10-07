from pathlib import Path

import json
import logging


LOGGER = logging.getLogger(__name__)

OUTPUT_DIR = Path("data") / "news_issues"


def output_path(
    name: str,
    exchange: str,
) -> Path:
    return OUTPUT_DIR / exchange.lower() / f"{name}.json"


def write_json(
    data: dict | list,
    name: str,
    exchange: str,
) -> None:
    path = output_path(name=name, exchange=exchange)
    path.parent.mkdir(parents=True, exist_ok=True)

    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    LOGGER.info("Saved %s", path)


def read_json(
    name: str,
    exchange: str,
) -> dict | list:
    path = output_path(name=name, exchange=exchange)
    return json.loads(path.read_text(encoding="utf-8"))
