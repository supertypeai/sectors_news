from datetime import datetime 
from urllib.parse import urljoin

from scraper_engine.base.scraper import Scraper

import argparse
import time
import logging


LOGGER = logging.getLogger(__name__)


class AsianTelecom(Scraper):
    def fetch_article_list(self, url: str) -> list:
        soup = self.fetch_news(url)

        if not soup:
            LOGGER.info("[Asian Telecom] [FAIL] Failed to fetch HTML or timed out for %s", url)
            return []

        return soup.select("div.item.with-border-bottom")

    def fetch_article_timestamp(self, article_url: str) -> str:
        soup = self.fetch_news(article_url)

        if not soup:
            return None

        time_tag = soup.select_one("time[pubdate][datetime]")

        if not time_tag:
            return None

        try:
            dt_obj = datetime.fromisoformat(time_tag["datetime"].replace("Z", "+00:00"))
            return dt_obj.strftime("%Y-%m-%d %H:%M:%S")
        
        except (ValueError, KeyError) as error:
            LOGGER.error("[Asian Telecom] Error parsing datetime '%s': %s", time_tag.get("datetime"), error)
            return None

    def parse_articles(self, article_items: list, target_date: str) -> tuple[list, bool]:
        parsed_articles = []
        reached_older_date = False

        target_datetime = datetime(
            int(target_date[:4]),
            int(target_date[4:6]),
            int(target_date[6:]),
        )

        for article_item in article_items:
            title_tag = article_item.select_one("h2.item__title a")
      
            title = title_tag.get_text(strip=True)
            source_url = urljoin("https://asiantelecom.com", title_tag.get("href"))

            thumbnail_tag = article_item.select_one("div.progressivePlain-container img")
            thumbnail_url = thumbnail_tag.get("src") if thumbnail_tag else None

            published_at = self.fetch_article_timestamp(source_url)
            time.sleep(0.5)
          
            if not published_at:
                LOGGER.info("[Asian Telecom] Failed to parse date for url: %s. Skipping.", source_url)
                continue

            article_datetime = datetime.strptime(published_at[:10], "%Y-%m-%d")
            
            if article_datetime < target_datetime:
                reached_older_date = True
                break

            parsed_articles.append({
                "title": title,
                "source": source_url,
                "thumbnail": thumbnail_url,
                "timestamp": published_at,
            })

        return parsed_articles, reached_older_date

    def extract_news_pages(self, num_pages: int, date: str) -> list:
        page_number = 0

        while True:
            page_url = f"https://asiantelecom.com/market/indonesia?page={page_number}"

            article_items = self.fetch_article_list(page_url)

            if not article_items:
                LOGGER.info("[Asian Telecom] No articles found on page %d, stopping.", page_number)
                break

            articles, reached_older_date = self.parse_articles(article_items, date)
            
            self.articles.extend(articles)
            LOGGER.info("[Asian Telecom] Page %d: %d articles collected.", page_number, len(articles))

            if reached_older_date:
                LOGGER.info("[Asian Telecom] Reached articles older than %s, stopping.", date)
                break

            if num_pages is not None and page_number >= num_pages:
                break

            page_number += 1
            time.sleep(1)

        LOGGER.info("[Asian Telecom] Total scraped: %d", len(self.articles))
        return self.articles


def main():
    scraper = AsianTelecom()

    parser = argparse.ArgumentParser(description="Script for scraping data from Asian Telecom")
    parser.add_argument("date", type=str)
    parser.add_argument("filename", type=str, nargs="?", default="asiantelecom")
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
    uv run -m src.scraper_engine.sources.idx.scrape_asian_telekom <date> [filename] [--pages N] [--csv]

    Examples:
    uv run -m src.scraper_engine.sources.idx.scrape_asian_telekom 20260427
    uv run -m src.scraper_engine.sources.idx.scrape_asian_telekom 20260427 test_asian_telecom
    uv run -m src.scraper_engine.sources.idx.scrape_asian_telekom 20260427 test_asian_telecom --pages 3 --csv
    """
    main()