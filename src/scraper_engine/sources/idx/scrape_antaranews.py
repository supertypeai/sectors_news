from datetime import datetime 

from scraper_engine.base.scraper import Scraper
from scraper_engine.sources.utils.constant import INDONESIAN_MONTHS

import argparse
import time
import logging


LOGGER = logging.getLogger(__name__)


class AntaraNews(Scraper):
    def fetch_article_list(self, url: str) -> list:
        soup = self.fetch_news(url)

        if not soup:
            LOGGER.info("[Antara News] [FAIL] Failed to fetch HTML or timed out for %s", url)
            return []

        article_lists =  soup.select("div.card__post.card__post-list.card__post__transition")

        return article_lists

    def fetch_article_timestamp(self, article_url: str) -> str:
        soup = self.fetch_news(article_url)

        if not soup:
            return None

        date_span = soup.select_one("div.wrap__article-detail-info span.text-secondary")

        if not date_span:
            return None

        return self.parse_timestamp(date_span.get_text(strip=True))

    def parse_timestamp(self, raw_timestamp: str) -> str:
        if not raw_timestamp:
            return None

        try:
            cleaned = raw_timestamp.strip()

            if "," in cleaned:
                cleaned = cleaned.split(", ", 1)[-1]

            for timezone_label in ["WIB", "WITA", "WIT"]:
                cleaned = cleaned.replace(timezone_label, "")

            cleaned = cleaned.strip()

            parts = cleaned.split()
            day = int(parts[0])
            month = INDONESIAN_MONTHS.get(parts[1])
            year = int(parts[2])
            hour, minute = parts[3].split(":")

            if not month:
                return None

            parsed_date = datetime(year, month, day, int(hour), int(minute))
            return parsed_date.strftime("%Y-%m-%d %H:%M:%S")

        except (ValueError, IndexError, AttributeError) as error:
            LOGGER.error("[Antara News] Error parsing date '%s': %s", raw_timestamp, error)
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
            title_tag = article_item.select_one("div.card__post__title h2.h5 a")

            title = title_tag.get_text(strip=True)
            source_url = title_tag.get("href")

            if not source_url:
                continue

            thumbnail_tag = article_item.select_one("div.col-md-5 img.img-fluid")
            thumbnail_url = thumbnail_tag["data-src"] if thumbnail_tag else None

            published_at = self.fetch_article_timestamp(source_url)
            time.sleep(0.5)

            if not published_at:
                LOGGER.info("[Antara News] Failed to parse date for url: %s. Skipping.", source_url)
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
        page_number = 1

        while True:
            page_url = f"https://www.antaranews.com/ekonomi/bursa/{page_number}"

            article_items = self.fetch_article_list(page_url)

            if not article_items:
                LOGGER.info("[Antara News] No articles found on page %d, stopping.", page_number)
                break
            
            articles, reached_older_date = self.parse_articles(article_items, date)

            self.articles.extend(articles)
            LOGGER.info("[Antara News] Page %d: %d articles collected.", page_number, len(articles))

            if reached_older_date:
                LOGGER.info("[Antara News] Reached articles older than %s, stopping.", date)
                break

            if num_pages is not None and page_number >= num_pages:
                break

            page_number += 1
            time.sleep(1)

        LOGGER.info("[Antara News] Total scraped: %d", len(self.articles))
        return self.articles


def main():
    scraper = AntaraNews()

    parser = argparse.ArgumentParser(description="Script for scraping data from Antara News")
    parser.add_argument("date", type=str)
    parser.add_argument("filename", type=str, nargs="?", default="antaranews")
    parser.add_argument("--pages", type=int, default=None, help="Number of pages to scrape (default: all)")
    parser.add_argument("--csv", action="store_true", help="Flag to indicate write to csv file")

    args = parser.parse_args()

    scraper.extract_news_pages(args.pages, args.date)
    scraper.write_json(scraper.articles, args.filename)

    if args.csv:
        scraper.write_csv(scraper.articles, args.filename)


if __name__ == "__main__":
    '''
    How to run:
    uv run -m src.scraper_engine.sources.idx.scrape_antaranews <date> [filename] [--pages N] [--csv]

    Examples:
    uv run -m src.scraper_engine.sources.idx.scrape_antaranews 20260427
    uv run -m src.scraper_engine.sources.idx.scrape_antaranews 20260430 test_antaranews
    uv run -m src.scraper_engine.sources.idx.scrape_antaranews 20260427 test_antaranews --pages 3 --csv
    '''
    main()
