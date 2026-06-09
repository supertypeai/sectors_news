from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup

from scraper_engine.base.scraper import Scraper, SeleniumScraper

import argparse
import logging
import time


LOGGER = logging.getLogger(__name__)


class NextInsight(SeleniumScraper):
    BASE_URL = "https://nextinsight.net"
    ARCHIVE_URL = "https://nextinsight.net/story-archive-mainmenu-60/949-2026"

    def fetch_article_list(self, url: str) -> list:
        raw_html_content = self.fetch_news_with_proxy(target_url=url)

        soup = BeautifulSoup(raw_html_content, "html.parser")

        article_items = soup.select("tr.cat-list-row0, tr.cat-list-row1")
        
        return article_items if article_items else []

    def fetch_article_content(self, article_url: str) -> tuple[str | None, str | None]:
        html = self.fetch_news_with_proxy(article_url)

        if not html:
            return None, None

        soup = BeautifulSoup(html, "html.parser")

        time_tag = soup.select_one("dd.published time[datetime]")
        published_at = self.parse_timestamp(time_tag.get("datetime")) if time_tag else None

        text_spans = soup.select('span[style*="font-size: 14pt"]')
        
        article_text = "\n\n".join(
            span.get_text(separator="\n", strip=True)
            for span in text_spans
            if span.get_text(strip=True)
        )

        return published_at, article_text or None

    def parse_timestamp(self, raw_timestamp: str) -> str:
        if not raw_timestamp:
            return None

        try:
            dt = datetime.fromisoformat(raw_timestamp)

            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)

            return dt.astimezone(ZoneInfo("Asia/Singapore"))

        except (ValueError, AttributeError) as error:
            LOGGER.error("[NextInsight] Failed to parse timestamp '%s': %s", raw_timestamp, error)
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
            title_tag = article_item.select_one("a")
            title = title_tag.get_text(strip=True) if title_tag else None
            relative_url = title_tag.get("href") if title_tag else None
            source_url = f"{self.BASE_URL}{relative_url}" if relative_url else None

            if not source_url or 'analyst say' in title.lower():
                continue

            published_at, article_text = self.fetch_article_content(source_url)
            time.sleep(0.3)

            if not published_at:
                LOGGER.info("[NextInsight] Failed to parse timestamp for %s. Skipping.", source_url)
                continue

            if published_at < target_datetime:
                reached_older_date = True
                break

            parsed_articles.append({
                "title": title,
                "source": source_url,
                "thumbnail": None,
                "timestamp": published_at.strftime("%Y-%m-%d %H:%M:%S"),
                "article": article_text
            })

        return parsed_articles, reached_older_date

    def extract_news_pages(self, num_pages: int, date: str) -> list:
        offset = 0
        page_count = 0

        while True:
            page_url = f"{self.ARCHIVE_URL}?start={offset}"
            
            article_items = self.fetch_article_list(page_url)

            if not article_items:
                LOGGER.info("[NextInsight] No articles found at offset %d, stopping.", offset)
                break

            articles, reached_older_date = self.parse_articles(article_items, date)

            self.articles.extend(articles)
            LOGGER.info("[NextInsight] Offset %d: %d articles collected.", offset, len(articles))

            if reached_older_date:
                LOGGER.info("[NextInsight] Reached articles older than %s, stopping.", date)
                break

            page_count += 1

            if num_pages is not None and page_count >= num_pages:
                break

            offset += 10
            time.sleep(1)

        LOGGER.info("[NextInsight] Total scraped: %d", len(self.articles))
        return self.articles


def main():
    scraper = NextInsight()

    parser = argparse.ArgumentParser(description="Script for scraping data from nextinsight.net")
    parser.add_argument("date", type=str)
    parser.add_argument("filename", type=str, nargs="?", default="nextinsight")
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
    uv run -m src.scraper_engine.sources.sgx.scrape_nextinsight <date> [filename] [--pages N] [--csv]

    Examples:
    uv run -m src.scraper_engine.sources.sgx.scrape_nextinsight 20260427
    uv run -m src.scraper_engine.sources.sgx.scrape_nextinsight 20260427 test_nextinsight
    uv run -m src.scraper_engine.sources.sgx.scrape_nextinsight 20260427 test_nextinsight --pages 3 --csv
    """
    main()