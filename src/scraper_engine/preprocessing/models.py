from dataclasses import dataclass


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
    dimension: dict
    structured_body: dict 
    score: int
    thumbnail: str | None = None

    @classmethod
    def try_create(
        cls,
        *,
        title: str,
        body: str,
        source: str,
        timestamp: str,
        sector: str | None,
        sub_sector: list[str],
        tags: list[str],
        tickers: list[str],
        structured_body: dict | None,
        dimension: dict | None,
        score: int | None,
        thumbnail: str | None = None,
    ) -> "News | None":
        if (
            not title
            or not body
        ):
            return None

        return cls(
            title=title,
            body=body,
            source=source,
            timestamp=timestamp,
            sector=sector,
            sub_sector=sub_sector,
            tags=tags,
            tickers=tickers,
            dimension=dimension,
            structured_body=structured_body,
            score=score,
            thumbnail=thumbnail,
        )

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
            "structured_body": self.structured_body,
            "score": self.score,
        }

        if self.thumbnail is not None:
            result["thumbnail"] = self.thumbnail

        return result
