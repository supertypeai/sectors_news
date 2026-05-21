from datetime import datetime

from scraper_engine.base.scraper import Scraper

import argparse
import logging
import time
import dateparser


LOGGER = logging.getLogger(__name__)


class MinerbaScraper(Scraper):
    def fetch_article_list(self, url: str) -> list:
        soup = self.fetch_news(url)

        if not soup:
            return []

        return soup.find_all("article")

    def parse_articles(self, article_items: list, target_date: str) -> tuple[list, bool]:
        parsed_articles = []
        reached_older_date = False

        target_datetime = datetime(
            int(target_date[:4]),
            int(target_date[4:6]),
            int(target_date[6:]),
        )

        for article_item in article_items:
            header = article_item.find("header")

            if not header:
                continue

            address_tag = header.find("address")

            if not address_tag:
                continue

            anchor_tag = address_tag.find("a")

            if not anchor_tag:
                continue

            title = anchor_tag.get_text(strip=True)
            source = anchor_tag.get("href", "").strip()

            if not title or not source:
                continue

            thumbnail_img = article_item.find("img", class_="imgl")
            thumbnail_url = thumbnail_img.get("src") if thumbnail_img else None

            time_tag = header.find("time")
            raw_timestamp = time_tag.get_text(strip=True) if time_tag else None
            
            if not raw_timestamp:
                LOGGER.info("[MINERBA] Missing datetime attribute for %s. Skipping.", source)
                continue

            published_at = dateparser.parse(raw_timestamp)

            if published_at < target_datetime:
                reached_older_date = True
                break

            parsed_articles.append({
                "title": title,
                "source": source,
                "thumbnail": thumbnail_url,
                "timestamp": published_at.strftime("%Y-%m-%d %H:%M:%S"),
            })

        return parsed_articles, reached_older_date

    def extract_news_pages(self, num_pages: int, date: str) -> list:
        base_url = "https://www.minerba.esdm.go.id/berita/minerba"
        page_number = 1

        while True:
            page_url = f"{base_url}/{page_number}"

            article_items = self.fetch_article_list(page_url)

            if not article_items:
                LOGGER.info("[MINERBA] No articles found on page %d, stopping.", page_number)
                break

            articles, reached_older_date = self.parse_articles(article_items, date)

            self.articles.extend(articles)
            LOGGER.info("[MINERBA] Page %d: %d articles collected.", page_number, len(articles))

            if reached_older_date:
                LOGGER.info("[MINERBA] Reached articles older than %s, stopping.", date)
                break

            if num_pages is not None and page_number >= num_pages:
                break

            page_number += 1
            time.sleep(1)

        LOGGER.info("[MINERBA] Total scraped: %d", len(self.articles))
        return self.articles


def main():
    scraper = MinerbaScraper()

    parser = argparse.ArgumentParser(
        description="Script for scraping data from minerba"
    )
    parser.add_argument("date", type=str)
    parser.add_argument("filename", type=str, nargs="?", default="minerbaarticles")
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
    uv run -m scraper_engine.sources.idx.scrape_minerba <date> [filename] [--pages N] [--csv]

    Examples:
    uv run -m scraper_engine.sources.idx.scrape_minerba 20260521
    uv run -m scraper_engine.sources.idx.scrape_minerba 20260521 test_minerba
    uv run -m scraper_engine.sources.idx.scrape_minerba 20260521 test_minerba --pages 3 --csv
    """
    main()