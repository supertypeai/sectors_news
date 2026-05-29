from bs4 import BeautifulSoup

from scraper_engine.base.scraper import Scraper
from scraper_engine.sources.idx.utils.time_parser import parse_relative_time

import argparse
import time
import logging 


LOGGER = logging.getLogger(__name__)


class CNNEkonomi(Scraper):
    def fetch_article_list(self, url: str) -> tuple[list, bool]:
        raw = self.fetch_news_with_proxy(url)
        soup = BeautifulSoup(raw, "html.parser")

        if not soup:
            return []

        article_items = soup.select("article.flex-grow")

        return article_items

    def parse_articles(self, article_items: list) -> list:
        parsed_articles = []

        for article_item in article_items:
            anchor_tag = article_item.select_one("a")
            source_url = anchor_tag["href"] if anchor_tag else None

            title_tag = article_item.select_one("h2")
            title = title_tag.get_text(strip=True) if title_tag else None

            thumbnail_tag = article_item.select_one("img")
            thumbnail_url = thumbnail_tag["src"] if thumbnail_tag else None

            raw_date = ""
            date_tag = article_item.select_one("span.text-xs.text-cnn_black_light3")
            
            if date_tag:
                raw_date = date_tag.get_text(strip=True)

            published_at = parse_relative_time(raw_date)

            if not published_at:
                LOGGER.warning("[CNN Ekonomi] Could not parse timestamp '%s' for %s", raw_date, source_url)

            parsed_articles.append({
                "title": title,
                "source": source_url,
                "thumbnail": thumbnail_url,
                "timestamp": published_at,
            })

        return parsed_articles

    def extract_news_pages(self, num_pages: int, date: str) -> list:
        base_url = "https://www.cnnindonesia.com/ekonomi/indeks/5"

        year = date[:4]
        month = date[4:6]
        day = date[6:]

        page_number = 1

        while True:
            full_url = f"{base_url}?date={year}/{month}/{day}&page={page_number}"

            article_items = self.fetch_article_list(full_url)

            if not article_items:
                LOGGER.info("[CNN Ekonomi] No articles found on page %d, stopping.", page_number)
                break

            articles = self.parse_articles(article_items)
            self.articles.extend(articles)
            LOGGER.info("[CNN Ekonomi] Page %d: %d articles collected.", page_number, len(articles))

            if num_pages is not None and page_number >= num_pages:
                break

            page_number += 1
            time.sleep(1)

        LOGGER.info("[CNN Ekonomi] Total scraped: %d", len(self.articles))
        return self.articles
  
  
def main():
    scraper = CNNEkonomi()

    parser = argparse.ArgumentParser(description="Script for scraping data from cnn ekonomi")

    parser.add_argument("date", type=str)
    parser.add_argument("filename", type=str, nargs="?", default="cnnekonomi")
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
    uv run -m src.scraper_engine.sources.idx.scrape_cnn_ekonomi <date> [filename] [--pages N] [--csv]

    Examples:
    uv run -m src.scraper_engine.sources.idx.scrape_cnn_ekonomi 20260427
    uv run -m src.scraper_engine.sources.idx.scrape_cnn_ekonomi 20260427 test_cnbc_ekonomi
    uv run -m src.scraper_engine.sources.idx.scrape_cnn_ekonomi 20260427 test_cnbc_ekonomi --pages 3 --csv
    """
    main()

