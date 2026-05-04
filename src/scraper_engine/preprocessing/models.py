from dataclasses import dataclass
from typing import Optional


@dataclass
class News:
    title: str
    body: str
    source: str
    timestamp: str
    sector: str
    sub_sector: list
    tags: list
    tickers: list
    dimension: Optional[dict]
    score: Optional[int]
    thumbnail: Optional[str] = None

    def to_dict(self) -> dict:
        result = {
            "title": self.title,
            "body": self.body,
            "source": self.source,
            "timestamp": self.timestamp,
            "sector": self.sector,
            "sub_sector": self.sub_sector,
            "tags": self.tags,
            "tickers": self.tickers,
            "dimension": self.dimension,
            "score": self.score,
        }

        if self.thumbnail is not None:
            result["thumbnail"] = self.thumbnail

        return result
