import csv
import json
from pathlib import Path


def read_json(path: str | Path) -> dict | list:
    json_path = Path(path)
    return json.loads(json_path.read_text(encoding="utf-8"))


def write_json(path: str | Path, payload: dict | list, indent: int = 2) -> None:
    json_path = Path(path)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(
        json.dumps(payload, indent=indent),
        encoding="utf-8",
    )


def write_csv(path: str | Path, data: list[dict]) -> None:
    csv_path = Path(path)
    csv_path.parent.mkdir(parents=True, exist_ok=True)

    with csv_path.open("w", newline="", encoding="utf-8") as csv_file:
        csv_writer = csv.writer(csv_file)
        header = data[0].keys()
        csv_writer.writerow(header)

        for item in data:
            csv_writer.writerow(item.values())
