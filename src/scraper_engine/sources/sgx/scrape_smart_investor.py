from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup

from scraper_engine.base.scraper import SeleniumScraper
from scraper_engine.config.conf import HEADERS

import argparse
import logging
import time
import requests 


LOGGER = logging.getLogger(__name__)


class TheSmartInvestor(SeleniumScraper):
    def fetch_article_list(self, url: str) -> list:
        response = requests.get(
            url=url, 
            headers=HEADERS
        )

        if response.status_code != 200:
            return []
        
        return response.json()

    def parse_timestamp(self, raw_timestamp: str) -> str:
        if not raw_timestamp:
            return None

        try:
            dt = datetime.fromisoformat(raw_timestamp)

            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)

            return dt.astimezone(ZoneInfo("Asia/Singapore"))

        except (ValueError, AttributeError) as error:
            LOGGER.error("[AsiaNews] Failed to parse timestamp '%s': %s", raw_timestamp, error)
            return None

    def parse_articles(self, article_items: list, target_date: str) -> tuple[list, bool]:
        parsed_articles = []
        reached_older_date = False

        target_datetime = datetime(
            int(target_date[:4]),
            int(target_date[4:6]),
            int(target_date[6:]),
            tzinfo=ZoneInfo("Asia/Singapore"),
        )

        for post in article_items:
            if "wc-memberships-restriction-message" in post["content"]["rendered"]:
                LOGGER.info("[The Smart Investor] Skipping premium article: %s", post["title"]["rendered"])
                continue

            title = post["title"]["rendered"]
            source_url = post["link"]
            published_at = self.parse_timestamp(post["date_gmt"])

            if not published_at:
                continue

            if published_at < target_datetime:
                reached_older_date = True
                break

            thumbnail_url = post.get("featured_image_src") or None

            content_soup = BeautifulSoup(post["content"]["rendered"], "html.parser")
            article_body = content_soup.get_text(separator="\n", strip=True)
            
            parsed_articles.append({
                "title": title,
                "source": source_url,
                "thumbnail": thumbnail_url,
                "timestamp": published_at.strftime("%Y-%m-%d %H:%M:%S"),
                'article': article_body
            })

        return parsed_articles, reached_older_date

    def extract_news_pages(self, num_pages: int, date: str) -> list:
        base_url = "https://thesmartinvestor.com.sg/wp-json/wp/v2/posts?"
        page_number = 1

        while True:
            page_url = f"{base_url}&page={page_number}"

            article_items = self.fetch_article_list(page_url)

            if not article_items:
                LOGGER.info("[AsiaNews] No articles found on page %d, stopping.", page_number)
                break

            articles, reached_older_date = self.parse_articles(article_items, date)

            self.articles.extend(articles)
            LOGGER.info("[AsiaNews] Page %d: %d articles collected.", page_number, len(articles))

            if reached_older_date:
                LOGGER.info("[AsiaNews] Reached articles older than %s, stopping.", date)
                break

            if num_pages is not None and page_number >= num_pages:
                break

            page_number += 1
            print(page_number)
            time.sleep(1)

        LOGGER.info("[AsiaNews] Total scraped: %d", len(self.articles))
        return self.articles


def main():
    scraper = TheSmartInvestor()

    parser = argparse.ArgumentParser(description="Script for scraping data from thesmartinvestor")
    parser.add_argument("date", type=str)
    parser.add_argument("filename", type=str, nargs="?", default="the_smart_investor")
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
    uv run -m src.scraper_engine.sources.sgx.scrape_smart_investor <date> [filename] [--pages N] [--csv]

    Examples:
    uv run -m src.scraper_engine.sources.sgx.scrape_smart_investor 20260427
    uv run -m src.scraper_engine.sources.sgx.scrape_smart_investor 20260427 test_scrape_the_smart_investor
    uv run -m src.scraper_engine.sources.sgx.scrape_smart_investor 20260427 test_scrape_the_smart_investor --pages 3 --csv
    """
    main()