from datetime import datetime
from zoneinfo import ZoneInfo

from scraper_engine.base.scraper import Scraper

import argparse
import json
import logging


LOGGER = logging.getLogger(__name__)


class ZaobaoSG(Scraper):
    BASE_URL = "https://www.zaobao.com.sg"
    SINGAPORE_FINANCE_URL = f"{BASE_URL}/finance/singapore"
    SINGAPORE_TIMEZONE = ZoneInfo("Asia/Singapore")
    STREAM_PREFIX = "streamController.enqueue("

    def decode_turbo_stream(self, flat_data: list, index: int):
        # React Router turbo-stream: values are stored flat and referenced by
        # index objects encode keys as "_<key index>" and negative indexes
        # are special values (undefined, null, NaN, ...)
        if index < 0:
            return None

        value = flat_data[index]

        if isinstance(value, list):
            return [self.decode_turbo_stream(flat_data, item) for item in value]

        if isinstance(value, dict):
            return {
                flat_data[int(key[1:])]: self.decode_turbo_stream(flat_data, item)
                for key, item in value.items()
            }

        return value

    def fetch_article_list(self, url: str) -> list:
        soup = self.fetch_news(url)
        if soup is None:
            return []

        for script_tag in soup.find_all("script"):
            script_text = script_tag.string or ""

            if self.STREAM_PREFIX not in script_text:
                continue

            start = script_text.index(self.STREAM_PREFIX) + len(self.STREAM_PREFIX)
            end = script_text.rindex(");")

            try:
                flat_data = json.loads(json.loads(script_text[start:end]))
                loader_data = self.decode_turbo_stream(flat_data, 0)
            except (ValueError, IndexError, TypeError) as error:
                LOGGER.warning("[Zaobao] Failed to decode listing payload: %s", error)
                continue

            payload = (
                (loader_data or {})
                .get("loaderData", {})
                .get("section", {})
                .get("payload", {})
            )

            if payload.get("articles"):
                return payload["articles"]

        LOGGER.warning("[Zaobao] Article list not found: %s", url)
        return []

    def parse_articles(self, article_list: list, target_datetime: datetime) -> list:
        parsed_articles = []

        for article in article_list:
            if article.get("item_type") != "article":
                continue

            title = article.get("title")
            href = article.get("href")
            thumbnail = article.get("thumbnail")
            time_unix = article.get("timestamp")

            if not title or not href or not time_unix:
                continue

            source = f"{self.BASE_URL}{href}" if href.startswith("/") else href
            article_datetime = datetime.fromtimestamp(time_unix, tz=self.SINGAPORE_TIMEZONE)

            if article_datetime < target_datetime:
                continue

            parsed_articles.append({
                "title": title,
                "source": source,
                "thumbnail": thumbnail,
                "timestamp": article_datetime.strftime("%Y-%m-%d %H:%M:%S"),
            })

        return parsed_articles

    def extract_news_pages(self, num_pages: int | None, target_date: str) -> list:
        # The section page has no pagination, it always lists the latest articles
        target_datetime = datetime(
            int(target_date[:4]),
            int(target_date[4:6]),
            int(target_date[6:]),
            tzinfo=self.SINGAPORE_TIMEZONE,
        )

        article_list = self.fetch_article_list(self.SINGAPORE_FINANCE_URL)
        articles = self.parse_articles(article_list, target_datetime)
        self.articles.extend(articles)

        LOGGER.info("[Zaobao] Total scraped: %d", len(self.articles))
        return self.articles


def main():
    scraper = ZaobaoSG()

    parser = argparse.ArgumentParser(description="Script for scraping data from Zaobao Singapore finance")
    parser.add_argument("date", type=str)
    parser.add_argument("filename", type=str, nargs="?", default="zaobao")
    parser.add_argument("--pages", type=int, default=None, help="Unused, the section has no pagination")
    parser.add_argument("--csv", action="store_true", help="Flag to indicate write to csv file")

    args = parser.parse_args()

    scraper.extract_news_pages(args.pages, args.date)
    scraper.write_json(scraper.articles, args.filename)

    if args.csv:
        scraper.write_csv(scraper.articles, args.filename)


if __name__ == "__main__":
    """
    How to run:
    uv run -m src.scraper_engine.sources.sgx.scrape_zaobao <date> [filename] [--csv]

    Examples:
    uv run -m src.scraper_engine.sources.sgx.scrape_zaobao 20261005
    uv run -m src.scraper_engine.sources.sgx.scrape_zaobao 20261005 test_scrape_zaobao --csv
    """
    main()
