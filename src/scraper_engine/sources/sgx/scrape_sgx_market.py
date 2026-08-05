from datetime import datetime, timezone
from datetime import time as day_time
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from scraper_engine.base.scraper import Scraper, SeleniumScraper

import argparse
import logging
import time
import json 
import requests


LOGGER = logging.getLogger(__name__)


class SGXMarketUpdates(SeleniumScraper):
    SGX_TIMEZONE = ZoneInfo("Asia/Singapore")

    def build_sgx_market_updates_url(
        self,
        target_date: str,
        page_number: int = 1,
        page_size: int = 20,
    ) -> str:
        try:
            parsed_date = datetime.strptime(target_date, "%Y%m%d").date()

        except ValueError as error:
            raise ValueError(
                f"target_date must be in yyyymmdd format, got: {target_date}"
            ) from error

        start_datetime = datetime.combine(
            parsed_date,
            day_time.min,
            tzinfo=self.SGX_TIMEZONE,
        )

        end_datetime = datetime.combine(
            parsed_date,
            day_time(23, 59, 59),
            tzinfo=self.SGX_TIMEZONE,
        )

        variables = {
            "limit": page_size,
            "offset": (page_number - 1) * page_size,
            "fromDate": str(int(start_datetime.timestamp())),
            "fromDateFilterEnabled": True,
            "toDate": str(int(end_datetime.timestamp())),
            "toDateFilterEnabled": True,
            "lang": "EN",
        }

        query_parameters = {
            "queryId": (
                "09434be8973b96b28894aefc57aff9e6c1f8f9c6:"
                "market_updates_list"
            ),
            "variables": json.dumps(variables, separators=(",", ":")),
        }

        return (
            "https://api2.sgx.com/content-api?"
            f"{urlencode(query_parameters)}"
        )

    def fetch_sgx_market_updates(
        self,
        session: requests.Session,
        request_url: str,
        timeout_seconds: int = 10,
    ) -> list[dict]:
        request_headers = {
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
        }

        response = session.get(
            request_url,
            headers=request_headers,
            timeout=timeout_seconds,
        )

        response.raise_for_status()

        response = response.json()

        response = response.get("data").get("list").get("results")

        return response 

    def extract_news_pages(self, num_pages: int, date: str) -> list:
        base_url = "https://www.sgx.com"

        api_url = self.build_sgx_market_updates_url(
            target_date=date, 
            page_number=1,
            page_size=100
        )

        session = requests.session()

        article_lists = self.fetch_sgx_market_updates(
            session=session, 
            request_url=api_url
        )

        for article_list in article_lists: 
            data = article_list.get("data")
            news_url = data.get("link").get("url")
            title = data["title"]
            date_unix_timestamp = data["dateArticle"]
            
            final_news_url = f"{base_url}{news_url}"

            converted_datetime = datetime.fromtimestamp(
                date_unix_timestamp, 
                tz=self.SGX_TIMEZONE
            )

            # SGX market updates provide a date but no publication time.
            timestamp = converted_datetime.strftime("%Y-%m-%d 00:00:00")

            payload = {
                "title": title, 
                "timestamp": timestamp, 
                "source": final_news_url,
                "thumbnail": None 
            }

            self.articles.append(payload)

        LOGGER.info("[SGXMarketUpdates] Total scraped: %d", len(self.articles))
        
        return self.articles


def main():
    scraper = SGXMarketUpdates()

    parser = argparse.ArgumentParser(description="Script for scraping data from scrape_sgx_market.net")
    parser.add_argument("date", type=str)
    parser.add_argument("filename", type=str, nargs="?", default="scrape_sgx_market")
    parser.add_argument("--pages", type=int, default=None, help="Number of pages to scrape (default: all)")
    parser.add_argument("--csv", action="store_true", help="Flag to indicate write to csv file")

    args = parser.parse_args()

    scraper.extract_news_pages(args.pages, args.date)
    scraper.write_json(scraper.articles, args.filename)

    if args.csv:
        scraper.write_csv(scraper.articles, args.filename)


if __name__ == "__main__":
    """
    How to run:
    uv run -m src.scraper_engine.sources.sgx.scrape_sgx_market <date> [filename] [--pages N] [--csv]

    Examples:
    uv run -m src.scraper_engine.sources.sgx.scrape_sgx_market 20260427
    uv run -m src.scraper_engine.sources.sgx.scrape_sgx_market 20260427 test_sgx_market_update
    uv run -m src.scraper_engine.sources.sgx.scrape_sgx_market 20260427 test_nextinsight --pages 3 --csv
    """
    main()
