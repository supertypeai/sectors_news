from datetime import datetime
from urllib.parse import urljoin
from zoneinfo import ZoneInfo
from goose3 import Goose

from scraper_engine.base.scraper import SeleniumScraper

import argparse
import logging
import time


LOGGER = logging.getLogger(__name__)


class TheEdgeReits(SeleniumScraper):
    BASE_URL = "https://www.theedgesingapore.com"
    SECTION_URL = f"{BASE_URL}/edgecollective/REITs-Report"

    def fetch_article_list(self, url: str) -> list:
        soup = self.fetch_news_with_selenium(
            url,
            wait_selector="article a[href]",
            time_sleep=2,
        )

        if not soup:
            LOGGER.warning("[The Edge REITs] Empty response for %s", url)
            return []

        article_items = soup.select("article")

        if not article_items:
            LOGGER.warning("[The Edge REITs] No article items found for %s", url)

        return article_items

    def fetch_article_content(
        self,
        article_url: str,
    ) -> tuple[datetime | None, str | None]:
        soup = self.fetch_news_with_selenium(
            article_url,
            wait_selector="time[datetime]",
            time_sleep=2,
        )

        if not soup:
            return None, None

        time_tag = soup.select_one("time[datetime]")
        raw_timestamp = time_tag.get("datetime") if time_tag else None
        published_at = self.parse_timestamp(raw_timestamp)

        article_data = Goose().extract(raw_html=str(soup).encode())
        article_body = article_data.cleaned_text or None

        return published_at, article_body

    def parse_timestamp(self, raw_timestamp: str | None) -> datetime | None:
        if not raw_timestamp:
            return None

        singapore_timezone = ZoneInfo("Asia/Singapore")

        try:
            published_at = datetime.fromisoformat(raw_timestamp)

            if published_at.tzinfo is None:
                published_at = published_at.replace(tzinfo=singapore_timezone)

            return published_at.astimezone(singapore_timezone)

        except (ValueError, AttributeError) as error:
            LOGGER.error(
                "[The Edge REITs] Failed to parse timestamp '%s': %s",
                raw_timestamp,
                error,
            )
            return None

    def parse_articles(self, article_items: list, target_date: str) -> tuple[list, bool]:
        parsed_articles = []
        reached_older_date = False

        target_datetime = datetime.strptime(target_date, "%Y%m%d").replace(
            tzinfo=ZoneInfo("Asia/Singapore")
        )

        for article_item in article_items:
            title_tag = article_item.select_one("h3")
            link_tag = article_item.select_one("a[href]")

            title = title_tag.get_text(" ", strip=True) if title_tag else None
            article_path = link_tag.get("href") if link_tag else None
            source_url = urljoin(self.BASE_URL, article_path) if article_path else None

            if not title or not source_url:
                continue

            image_tag = article_item.select_one("img[src]")
            thumbnail_url = image_tag.get("src") if image_tag else None

            published_at, article_body = self.fetch_article_content(source_url)
            time.sleep(0.3)

            if not published_at:
                LOGGER.info(
                    "[The Edge REITs] Failed to parse timestamp for %s. Skipping.",
                    source_url,
                )
                continue

            if published_at < target_datetime:
                reached_older_date = True
                continue

            parsed_articles.append(
                {
                    "title": title,
                    "source": source_url,
                    "thumbnail": thumbnail_url,
                    "timestamp": published_at.strftime("%Y-%m-%d %H:%M:%S"),
                    "article": article_body,
                }
            )

        return parsed_articles, reached_older_date

    # Keep _num_pages for ScraperCollection compatibility, only the latest page is scraped
    def extract_news_pages(self, _num_pages: int | None, date: str) -> list:
        article_items = self.fetch_article_list(self.SECTION_URL)

        if not article_items:
            LOGGER.info("[The Edge REITs] No articles found, stopping.")
            return self.articles

        articles, reached_older_date = self.parse_articles(article_items, date)
        self.articles.extend(articles)

        LOGGER.info("[The Edge REITs] Page 1: %d articles collected.", len(articles))

        if reached_older_date:
            LOGGER.info("[The Edge REITs] Ignored articles older than %s.", date)

        LOGGER.info("[The Edge REITs] Total scraped: %d", len(self.articles))
        return self.articles


def main():
    scraper = TheEdgeReits()

    parser = argparse.ArgumentParser(
        description="Script for scraping The Edge Singapore REITs Report"
    )
    parser.add_argument("date", type=str)
    parser.add_argument("filename", type=str, nargs="?", default="the_edge_reits")
    parser.add_argument(
        "--csv",
        action="store_true",
        help="Flag to indicate write to csv file",
    )

    args = parser.parse_args()

    try:
        scraper.extract_news_pages(None, args.date)
        scraper.write_json(scraper.articles, args.filename)

        if args.csv:
            scraper.write_csv(scraper.articles, args.filename)

    finally:
        scraper.close_shared_driver()


if __name__ == "__main__":
    """
    How to run:
    uv run -m scraper_engine.sources.sgx.scrape_the_edge_reits <date> [filename] [--csv]

    Examples:
    uv run -m scraper_engine.sources.sgx.scrape_the_edge_reits 20260424
    uv run -m scraper_engine.sources.sgx.scrape_the_edge_reits 20260424 the_edge_reits
    uv run -m scraper_engine.sources.sgx.scrape_the_edge_reits 20260424 the_edge_reits --csv
    """
    main()
