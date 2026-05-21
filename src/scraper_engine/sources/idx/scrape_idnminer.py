from datetime import datetime

from scraper_engine.base.scraper import Scraper

import argparse
import logging
import time
import dateparser


LOGGER = logging.getLogger(__name__)


class IdnMinerScraper(Scraper):
    def fetch_article_list(self, url: str) -> list:
        soup = self.fetch_news(url)
        
        if not soup:
            return []

        return soup.find_all("div", class_="col-12")

    def parse_articles(self, article_items: list, target_date: str) -> tuple[list, bool]:
        parsed_articles = []
        reached_older_date = False

        target_datetime = datetime(
            int(target_date[:4]),
            int(target_date[4:6]),
            int(target_date[6:])
        )

        for article_item in article_items:
            link_tag = article_item.find("a")

            if not link_tag or "href" not in link_tag.attrs:
                LOGGER.info("[IDNMINER] No anchor tag found in item. Skipping.")
                continue

            source = link_tag["href"].strip()

            if "/news/detail/" not in source:
                LOGGER.info("[IDNMINER] Non-news link found: %s. Skipping.", source)
                continue

            title_tag = link_tag.find("h5", class_="card-title")
            timestamp_container = link_tag.find("div", class_="mb-2 text-muted small")

            if not title_tag or not timestamp_container:
                LOGGER.info("[IDNMINER] Could not find title or timestamp for %s. Skipping.", source)
                continue

            title = title_tag.get_text(strip=True)

            thumbnail_img = link_tag.find("img", class_="img-fluid")
            thumbnail_url = thumbnail_img.get("src") if thumbnail_img else None

            text_parts = (
                timestamp_container
                .get_text(separator="|", strip=True)
                .split("|")
            )

            if not text_parts:
                LOGGER.info("[IDNMINER] Empty timestamp container for %s. Skipping.", source)
                continue

            raw_timestamp = text_parts[0]
            published_at = dateparser.parse(raw_timestamp)

            if not published_at:
                LOGGER.info("[IDNMINER] Failed to parse timestamp '%s' for %s. Skipping.", raw_timestamp, source)
                continue

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
        base_url = "https://indonesiaminer.com/news"
        page_number = 1

        while True:
            page_url = f"{base_url}?page={page_number}"

            article_items = self.fetch_article_list(page_url)
           
            if not article_items:
                LOGGER.info("[IDNMINER] No articles found on page %d, stopping.", page_number)
                break

            articles, reached_older_date = self.parse_articles(article_items, date)

            self.articles.extend(articles)
            LOGGER.info("[IDNMINER] Page %d: %d articles collected.", page_number, len(articles))

            if reached_older_date:
                LOGGER.info("[IDNMINER] Reached articles older than %s, stopping.", date)
                break

            if num_pages is not None and page_number >= num_pages:
                break

            page_number += 1
            time.sleep(1)

        LOGGER.info("[IDNMINER] Total scraped: %d", len(self.articles))
        return self.articles


def main():
    scraper = IdnMinerScraper()

    parser = argparse.ArgumentParser(
        description="Script for scraping data from indonesian miner"
    )
    parser.add_argument("date", type=str)
    parser.add_argument("filename", type=str, nargs="?", default="idnminerarticles")
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
    uv run -m scraper_engine.sources.idx.scrape_idnminer <date> [filename] [--pages N] [--csv]

    Examples:
    uv run -m scraper_engine.sources.idx.scrape_idnminer 20260521
    uv run -m scraper_engine.sources.idx.scrape_idnminer 20260521 test_idnminer
    uv run -m scraper_engine.sources.idx.scrape_idnminer 20260521 test_idnminer --pages 3 --csv
    """
    main()