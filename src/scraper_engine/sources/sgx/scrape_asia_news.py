from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from scraper_engine.base.scraper import SeleniumScraper

import argparse
import logging
import time


LOGGER = logging.getLogger(__name__)


class AsiaNews(SeleniumScraper):
    def fetch_article_list(self, url: str) -> list:
        soup = self.fetch_news(url=url)
        article_items = soup.select("article")

        return article_items if article_items else []

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

        for article_item in article_items:
            anchor_tag = article_item.select_one("h2.entry-title > a")

            if not anchor_tag:
                continue

            title = anchor_tag.get_text(strip=True)
            source_url = anchor_tag.get("href")

            if not title or not source_url:
                continue

            thumbnail_tag = article_item.select_one("div.post-thumb img")
            thumbnail_url = thumbnail_tag.get("data-src") if thumbnail_tag else None

            time_tag = article_item.select_one("time[datetime]")
            published_at = self.parse_timestamp(time_tag.get("datetime") if time_tag else None)

            if not published_at:
                LOGGER.info("[AsiaNews] Failed to parse timestamp for %s. Skipping.", source_url)
                continue

            if published_at < target_datetime:
                reached_older_date = True
                break

            parsed_articles.append({
                "title": title,
                "source": source_url,
                "thumbnail": thumbnail_url,
                "timestamp": published_at.strftime("%Y-%m-%d %H:%M:%S"),
            })

        return parsed_articles, reached_older_date

    def extract_news_pages(self, num_pages: int, date: str) -> list:
        base_url = "https://asianews.network/tag/singapore/page/"
        page_number = 1

        while True:
            page_url = f"{base_url}{page_number}/"

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
            time.sleep(1)

        LOGGER.info("[AsiaNews] Total scraped: %d", len(self.articles))
        return self.articles


def main():
    scraper = AsiaNews()

    parser = argparse.ArgumentParser(description="Script for scraping data from asianews")
    parser.add_argument("date", type=str)
    parser.add_argument("filename", type=str, nargs="?", default="asia_news")
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
    uv run -m src.scraper_engine.sources.sgx.scrape_asia_news <date> [filename] [--pages N] [--csv]

    Examples:
    uv run -m src.scraper_engine.sources.sgx.scrape_asia_news 20260427
    uv run -m src.scraper_engine.sources.sgx.scrape_asia_news 20260427 test_scrape_asia_news
    uv run -m src.scraper_engine.sources.sgx.scrape_asia_news 20260427 test_scrape_asia_news --pages 3 --csv
    """
    main()