from datetime import datetime
from zoneinfo import ZoneInfo

from scraper_engine.base.scraper import Scraper

import requests
import logging 
import argparse 
import urllib.parse
import json 


LOGGER = logging.getLogger(__name__)


class ChannelNewsAsiaSG(Scraper):
    def parse_articles(self, response_data: dict, target_datetime: datetime) -> tuple[list, bool]:
        article_list = response_data.get("results", [{}])[0].get("hits") or []

        if not article_list:
            return [], False

        parsed_articles = []
        reached_older_date = False

        for article in article_list:
            source = article.get("link_absolute")
            thumbnail = article.get("hero_image_url")
            title = article.get("title")
            time_unix = article.get("field_release_date")

            if not thumbnail or not source:
                continue 

            article_datetime = self.normalize_timestamp(time_unix)

            if not article_datetime:
                LOGGER.info("[CNA SG] Failed to parse timestamp for %s. Skipping.", source)
                continue

            if article_datetime < target_datetime:
                reached_older_date = True
                break

            parsed_articles.append({
                "title": title,
                "source": source,
                "thumbnail": thumbnail,
                "timestamp": article_datetime.strftime("%Y-%m-%d %H:%M:%S"),
            })

        return parsed_articles, reached_older_date

    def normalize_timestamp(self, time_unix: int) -> datetime | None:
        try:
            return datetime.fromtimestamp(time_unix, tz=ZoneInfo("Asia/Singapore"))

        except Exception as error:
            LOGGER.error("[CNA SG] Error converting timestamp: %s", error)
            return None

    def extract_news_pages(self, num_pages: int, target_date: str) -> list:
        target_datetime = datetime(
            int(target_date[:4]),
            int(target_date[4:6]),
            int(target_date[6:]),
            tzinfo=ZoneInfo("Asia/Singapore"),
        )

        url = "https://KKWFBQ38XF-dsn.algolia.net/1/indexes/*/queries"

        headers = {
            "x-algolia-application-id": "KKWFBQ38XF",
            "x-algolia-api-key": "e4b61225b5a00162761c501328a58ac7",
            "content-type": "application/json",
        }

        facet_filters = json.dumps([["categories:Singapore", "categories:News"], ["type:article"]])

        page_number = 0

        while True:
            payload = {
                "requests": [
                    {
                        "indexName": "cnarevamp-ezrqv5hx",
                        "params": f"query=&page={page_number}&hitsPerPage=10&facetFilters={urllib.parse.quote(facet_filters)}",
                    }
                ]
            }

            response = requests.post(url, headers=headers, json=payload)
            response_data = response.json()

            articles, reached_older_date = self.parse_articles(response_data, target_datetime)

            self.articles.extend(articles)
            LOGGER.info("[CNA SG] Page %d: %d articles collected.", page_number, len(articles))

            if reached_older_date:
                LOGGER.info("[CNA SG] Reached articles older than %s, stopping.", target_date)
                break

            if num_pages is not None and page_number >= num_pages:
                break

            page_number += 1

        LOGGER.info("[CNA SG] Total scraped: %d", len(self.articles))
        return self.articles


def main():
    scraper = ChannelNewsAsiaSG()

    parser = argparse.ArgumentParser(description="Script for scraping data from CNA")
    parser.add_argument("date", type=str)
    parser.add_argument("filename", type=str, nargs="?", default="cna")
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
    uv run -m src.scraper_engine.sources.sgx.scrape_cna <date> [filename] [--pages N] [--csv]

    Examples:
    uv run -m src.scraper_engine.sources.sgx.scrape_cna 20260427
    uv run -m src.scraper_engine.sources.sgx.scrape_cna 20260427 test_scrape_cna
    uv run -m src.scraper_engine.sources.sgx.scrape_cna 20260427 test_scrape_cna --pages 3 --csv
    """
    main()