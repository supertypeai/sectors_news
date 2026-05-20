from datetime import datetime
from zoneinfo import ZoneInfo

from scraper_engine.base.scraper import Scraper

import requests
import logging
import argparse


LOGGER = logging.getLogger(__name__)


class StraitsTimes(Scraper):
    ROOT_URL = "https://www.straitstimes.com"

    def normalize_timestamp(self, iso_str: str) -> datetime | None:
        if not iso_str:
            return None

        try:
            dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
            return dt.astimezone(ZoneInfo("Asia/Singapore"))

        except ValueError as error:
            LOGGER.error("[ST SG] Failed to parse timestamp '%s': %s", iso_str, error)
            return None

    def parse_articles(
        self, 
        response_data: dict, 
        target_datetime: datetime
    ) -> tuple[list, bool]:
        cards = response_data.get("cards", [])

        if not cards:
            return [], False

        parsed_articles = []
        reached_older_date = False

        for card in cards:
            article_card = card.get("articleCard")

            if not article_card:
                continue

            title = article_card.get("title", "")
            relative_url = article_card.get("urlPath", "")

            media = article_card.get("media") or {}
            
            thumbnail = ''
            for item in media: 
                image = item.get("image") or {}
                thumbnail = image.get("src")

            raw_timestamp = article_card.get("publishedDate", "")
            article_datetime = self.normalize_timestamp(raw_timestamp)

            if not article_datetime:
                LOGGER.info("[ST SG] Failed to parse timestamp for %s. Skipping.", relative_url)
                continue

            if article_datetime < target_datetime:
                reached_older_date = True
                break

            parsed_articles.append({
                "title": title,
                "source": f"{self.ROOT_URL}{relative_url}",
                "thumbnail": thumbnail,
                "timestamp": article_datetime.strftime("%Y-%m-%d %H:%M:%S"),
            })

        return parsed_articles, reached_older_date

    def extract_news_pages(self, num_pages: int | None, target_date: str) -> list:
        api_url = "https://www.straitstimes.com/_plat/api/v1/articlesListing"
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/91.0.4472.124 Safari/537.36"
            )
        }
        
        target_datetime = datetime(
            int(target_date[:4]),
            int(target_date[4:6]),
            int(target_date[6:]),
            tzinfo=ZoneInfo("Asia/Singapore"),
        )

        page_number = 1

        while True:
            params = {
                "pageType": "tags",
                "searchParam": "sgx",
                "page": page_number,
            }

            try:
                response = requests.get(api_url, params=params, headers=headers)
                response.raise_for_status()
                response_data = response.json()

            except Exception as error:
                LOGGER.error("[ST SG] Request failed on page %d: %s", page_number, error)
                break

            articles, reached_older_date = self.parse_articles(response_data, target_datetime)
            self.articles.extend(articles)

            LOGGER.info("[ST SG] Page %d: %d articles collected.", page_number, len(articles))

            if reached_older_date:
                LOGGER.info("[ST SG] Reached articles older than %s, stopping.", target_date)
                break

            if num_pages is not None and page_number >= num_pages:
                LOGGER.info("[ST SG] Reached page limit of %d, stopping.", num_pages)
                break

            page_number += 1

        LOGGER.info("[ST SG] Total scraped: %d", len(self.articles))
        return self.articles


def main():
    scraper = StraitsTimes()

    parser = argparse.ArgumentParser(description="Script for scraping data from Straits Times SG")
    parser.add_argument("date", type=str)
    parser.add_argument("filename", type=str, nargs="?", default="straitstimes")
    parser.add_argument("--pages", type=int, default=None, help="Number of pages to scrape (default: until target date reached)")
    parser.add_argument("--csv", action="store_true", help="Flag to indicate write to csv file")

    args = parser.parse_args()

    scraper.extract_news_pages(args.pages, args.date)
    scraper.write_json(scraper.articles, args.filename)

    if args.csv:
        scraper.write_csv(scraper.articles, args.filename)


if __name__ == "__main__":
    """
    How to run:
    uv run -m src.scraper_engine.sources.sgx.scrape_straits_times <date> [filename] [--pages N] [--csv]

    Examples:
    uv run -m src.scraper_engine.sources.sgx.scrape_straits_times 20260427
    uv run -m src.scraper_engine.sources.sgx.scrape_straits_times 20260427 test_scrape_st
    uv run -m src.scraper_engine.sources.sgx.scrape_straits_times 20260427 test_scrape_st --pages 3 --csv
    """
    main()