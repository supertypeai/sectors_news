from datetime import datetime
from zoneinfo import ZoneInfo
from scrapling.fetchers import Fetcher

from scraper_engine.base.scraper import Scraper

import time
import argparse
import logging


LOGGER = logging.getLogger(__name__)


class BusinessTimesSG(Scraper):
    BASE_URL = "https://www.businesstimes.com.sg"
    SINGAPORE_TIMEZONE = ZoneInfo("Asia/Singapore")
    PAGE_SIZE = 10
    MAX_PAGES = 20

    # Listing pages load more stories through these APIs (infinite scroll):
    # section pages page by `page`, keyword pages page by `offset`
    LISTINGS = [
        {
            "name": "keywords/sgx",
            "endpoint": "/_plat/api/v1/articles/tags",
            "params": {"urlPath": "/keywords/sgx"},
            "paging": "offset",
        },
        {
            "name": "singapore/economy-policy",
            "endpoint": "/_plat/api/v1/articles/sections",
            "params": {"sections": "singapore_economy-policy"},
            "paging": "page",
        },
        {
            "name": "companies-markets",
            "endpoint": "/_plat/api/v1/articles/sections",
            "params": {"sections": "companies-markets"},
            "paging": "page",
        },
    ]

    def fetch_listing_page(self, listing: dict, page_number: int) -> list:
        params = {**listing["params"], "size": self.PAGE_SIZE}

        if listing["paging"] == "offset":
            params["offset"] = (page_number - 1) * self.PAGE_SIZE
        else:
            params["page"] = page_number

        url = f"{self.BASE_URL}{listing['endpoint']}"

        try:
            response = Fetcher.get(
                url,
                params=params,
                stealthy_headers=True,
                impersonate="chrome",
            )

            if response.status != 200:
                LOGGER.warning("[BT SG] Non-200 status %d for %s", response.status, url)
                self.record_request_failure(
                    url=url,
                    reason="HTTPStatusError",
                    status_code=response.status,
                    message=f"Received status code {response.status}",
                )
                return []

            self.record_request_success(status_code=response.status)
            return (response.json().get("data") or {}).get("items") or []

        except Exception as error:
            LOGGER.error("[BT SG] Failed to fetch %s page %d: %s", listing["name"], page_number, error)
            self.record_request_failure(
                url=url,
                reason=type(error).__name__,
                message=str(error),
            )
            return []

    def normalize_timestamp(self, raw_time_str: str) -> datetime | None:
        if not raw_time_str:
            return None

        try:
            return datetime.fromisoformat(raw_time_str.replace("Z", "+00:00")).astimezone(
                self.SINGAPORE_TIMEZONE
            )

        except ValueError as error:
            LOGGER.error("[BT SG] Failed to parse timestamp '%s': %s", raw_time_str, error)
            return None

    def get_thumbnail(self, article_data: dict) -> str | None:
        for media in article_data.get("media") or []:
            if media.get("type") != "picture":
                continue

            for variant in ("landscape", "original"):
                if url := (media.get(variant) or {}).get("url"):
                    return url

        return None

    def parse_articles(
        self,
        items: list,
        target_datetime: datetime,
        seen_urls: set,
    ) -> tuple[list, bool]:
        parsed_articles = []
        has_recent_article = False

        for item in items:
            article_data = item.get("articleData") or {}

            title = article_data.get("title")
            url = (article_data.get("urlPath") or "").strip()

            if item.get("itemType") != "Article" or not title or not url:
                continue

            article_datetime = self.normalize_timestamp(article_data.get("publishTime"))

            if not article_datetime:
                LOGGER.info("[BT SG] Failed to parse timestamp for %s. Skipping.", url)
                continue

            # Listings are not strictly ordered by time, so only stop paging
            # once a whole page is older than the target date
            if article_datetime < target_datetime:
                continue

            has_recent_article = True

            if url in seen_urls:
                continue

            seen_urls.add(url)

            if article_data.get("paidMode") == "premium":
                LOGGER.info("[BT SG] Skipping subscriber article: %s", url)
                continue

            parsed_articles.append({
                "title": title,
                "source": url,
                "thumbnail": self.get_thumbnail(article_data),
                "timestamp": article_datetime.strftime("%Y-%m-%d %H:%M:%S"),
            })

        return parsed_articles, not has_recent_article

    def extract_news_pages(self, num_pages: int | None, target_date: str) -> list:
        target_datetime = datetime(
            int(target_date[:4]),
            int(target_date[4:6]),
            int(target_date[6:]),
            tzinfo=self.SINGAPORE_TIMEZONE,
        )

        max_pages = num_pages or self.MAX_PAGES
        seen_urls = set()

        for listing in self.LISTINGS:
            for page_number in range(1, max_pages + 1):
                items = self.fetch_listing_page(listing, page_number)

                if not items:
                    LOGGER.info("[BT SG] %s: no items on page %d, stopping.", listing["name"], page_number)
                    break

                articles, reached_older_date = self.parse_articles(
                    items, target_datetime, seen_urls
                )
                self.articles.extend(articles)

                LOGGER.info(
                    "[BT SG] %s page %d: %d articles collected.",
                    listing["name"],
                    page_number,
                    len(articles),
                )

                if reached_older_date:
                    LOGGER.info("[BT SG] %s: reached articles older than %s, stopping.", listing["name"], target_date)
                    break

                time.sleep(1)

        LOGGER.info("[BT SG] Total scraped: %d", len(self.articles))
        return self.articles


def main():
    scraper = BusinessTimesSG()

    parser = argparse.ArgumentParser(description="Script for scraping data from Business Times SG")
    parser.add_argument("date", type=str)
    parser.add_argument("filename", type=str, nargs="?", default="businesstimes")
    parser.add_argument("--pages", type=int, default=None, help="Max pages per listing (default: 20)")
    parser.add_argument("--csv", action="store_true", help="Flag to indicate write to csv file")

    args = parser.parse_args()

    scraper.extract_news_pages(args.pages, args.date)
    scraper.write_json(scraper.articles, args.filename)

    if args.csv:
        scraper.write_csv(scraper.articles, args.filename)


if __name__ == "__main__":
    """
    How to run:
    uv run -m src.scraper_engine.sources.sgx.scrape_business_times <date> [filename] [--pages N] [--csv]

    Examples:
    uv run -m src.scraper_engine.sources.sgx.scrape_business_times 20260427
    uv run -m src.scraper_engine.sources.sgx.scrape_business_times 20260427 test_scrape_bt
    uv run -m src.scraper_engine.sources.sgx.scrape_business_times 20260427 test_scrape_bt --pages 5 --csv
    """
    main()
