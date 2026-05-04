from datetime import datetime

from scraper_engine.base.scraper import Scraper

import argparse
import time
import logging 


LOGGER = logging.getLogger(__name__)


class EmitenNews(Scraper):
    def fetch_article_list(self, url: str) -> list:
        soup = self.fetch_news(url)

        if not soup:
            LOGGER.info("[Emiten News] [FAIL] Failed to fetch HTML or timed out for %s", url)
            return []

        wrapper = soup.select_one("div.search-result-wrapper")

        if not wrapper:
            LOGGER.info("[Emiten News] [FAIL] Target container 'search-result-wrapper' not found.")
            return []

        return wrapper.select("a.news-card-2.search-result-item")
    
    def parse_articles(self, article_items: list, target_date: str) -> list: 
        parsed_articles = []
        reached_older_date = False 
        
        target_datetime = datetime(
            int(target_date[:4]),
            int(target_date[4:6]),
            int(target_date[6:]),
        )

        for article_item in article_items:
            source_url = article_item.get("href")

            if not source_url:
                continue

            title_tag = article_item.select_one("p.fs-16")
            title = title_tag.get_text(strip=True) if title_tag else None

            thumbnail_tag = article_item.select_one("div.news-card-2-img img")
            thumbnail_url = thumbnail_tag.get("src") if thumbnail_tag else None

            published_at = self.fetch_article_timestamp(source_url)
            time.sleep(0.5)

            if not published_at:
                LOGGER.info("[Emiten News] Failed to parse date for url: %s. Skipping.", source_url)
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
    
    def fetch_article_timestamp(self, article_url: str) -> str:
        soup = self.fetch_news(article_url)

        if not soup:
            return None

        timestamp_tag = soup.select_one("span.time-posted")

        if not timestamp_tag:
            return None

        try:
            raw_text = timestamp_tag.get_text(strip=True)
            date_part = raw_text.split(",")[0].strip()
            return self.parse_timestamp(date_part)
        
        except (AttributeError, IndexError) as error:
            LOGGER.error("[Emiten News] Error extracting timestamp: %s", error)
            return None

    def parse_timestamp(self, raw_timestamp: str) -> str:
        if not raw_timestamp:
            return None

        try:
            parsed_date = datetime.strptime(raw_timestamp, "%d/%m/%Y")
            return parsed_date.strftime("%Y-%m-%d %H:%M:%S")
        
        except (ValueError, AttributeError) as error:
            LOGGER.error("[Emiten News] Error parsing date '%s': %s", raw_timestamp, error)
            return None

    def extract_news_pages(self, num_pages: int, date: str) -> list:
        base_url = "https://emitennews.com/category/emiten"
        page_number = 1
        offset = 1

        while True:
            page_url = f"{base_url}/{offset}"
            print(page_url)

            article_items = self.fetch_article_list(page_url)

            if not article_items:
                LOGGER.info("[Emiten News] No articles found on page %d, stopping.", page_number)
                break

            articles, reached_older_date = self.parse_articles(article_items, date)
            self.articles.extend(articles)
            LOGGER.info("[Emiten News] Page %d: %d articles collected.", page_number, len(articles))

            if reached_older_date:
                LOGGER.info("[Emiten News] Reached articles older than %s, stopping.", date)
                break

            if num_pages is not None and page_number >= num_pages:
                break

            page_number += 1
            offset += 9
            time.sleep(1)

        LOGGER.info("[Emiten News] Total scraped: %d", len(self.articles))
        return self.articles


def main():
    scraper = EmitenNews()

    parser = argparse.ArgumentParser(description="Script for scraping data from Emiten News")
    parser.add_argument("date", type=str)
    parser.add_argument("filename", type=str, nargs="?", default="emitennews")
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
    uv run -m src.scraper_engine.sources.idx.scrape_emiten_news <date> [filename] [--pages N] [--csv]

    Examples:
    uv run -m src.scraper_engine.sources.idx.scrape_emiten_news 20260427
    uv run -m src.scraper_engine.sources.idx.scrape_emiten_news 20260427 test_emiten
    uv run -m src.scraper_engine.sources.idx.scrape_emiten_news 20260427 test_emiten --pages 3 --csv
    """
    main()