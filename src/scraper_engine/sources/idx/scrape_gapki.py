from datetime import datetime

from scraper_engine.base.scraper import SeleniumScraper

import argparse
import logging
import time


LOGGER = logging.getLogger(__name__)


class GapkiScraper(SeleniumScraper):
    def fetch_article_list(self, url: str) -> list:
        soup = self.fetch_news_with_selenium(url, 40)

        if not soup:
            return []

        return soup.find_all("article", class_="post")

    def fetch_article_timestamp(self, article_url: str) -> datetime | None:
        soup = self.fetch_news_with_selenium(article_url)

        if not soup:
            return None

        meta_list = soup.select_one("ul.nv-meta-list")

        if not meta_list:
            return None

        time_tag = meta_list.select_one("time.updated[datetime]")

        if not time_tag:
            return None

        raw_datetime = time_tag.get("datetime", "").strip()

        if not raw_datetime:
            return None

        try:
            return datetime.fromisoformat(raw_datetime).replace(tzinfo=None)
        
        except ValueError as error:
            LOGGER.error("[GAPKI] Failed to parse timestamp '%s': %s", raw_datetime, error)
            return None

    def parse_articles(self, article_items: list, target_date: str) -> tuple[list, bool]:
        parsed_articles = []
        reached_older_date = False

        target_datetime = datetime(
            int(target_date[:4]),
            int(target_date[4:6]),
            int(target_date[6:])
        )

        for article_item in article_items:
            link_element = article_item.select_one(
                "h2.blog-entry-title a, .nv-post-thumbnail-wrap a"
            )

            if not link_element:
                LOGGER.info("[GAPKI] Could not find link element. Skipping.")
                continue

            title = link_element.get("title", "").strip()
            source = link_element.get("href", "").strip()

            if not title or not source:
                LOGGER.info("[GAPKI] Missing title or source. Skipping.")
                continue

            thumbnail_wrap = article_item.select_one(".nv-post-thumbnail-wrap img")
            thumbnail_url = thumbnail_wrap.get("src") if thumbnail_wrap else None

            published_at = self.fetch_article_timestamp(source)
        
            time.sleep(0.5)

            if not published_at:
                LOGGER.info("[GAPKI] Failed to fetch timestamp for %s. Skipping.", source)
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
        base_url = 'https://gapki.id/en/news/category/recent-news/page/'

        page_number = 1

        while True:
            page_url = f'{base_url}{page_number}'
           
            article_items = self.fetch_article_list(page_url)
            
            if not article_items:
                LOGGER.info("[GAPKI] No articles found on page %d, stopping.", page_number)
                break

            articles, reached_older_date = self.parse_articles(article_items, date)

            self.articles.extend(articles)
            LOGGER.info("[GAPKI] Page %d: %d articles collected.", page_number, len(articles))

            if reached_older_date:
                LOGGER.info("[GAPKI] Reached articles older than %s, stopping.", date)
                break

            if num_pages is not None and page_number >= num_pages:
                break

            page_number += 1
            time.sleep(1)

        LOGGER.info("[GAPKI] Total scraped: %d", len(self.articles))
        return self.articles


def main():
    scraper = GapkiScraper()

    parser = argparse.ArgumentParser(
        description="Script for scraping data from gapki"
    )
    parser.add_argument("date", type=str)
    parser.add_argument("filename", type=str, nargs="?", default="gapkiarticles")
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
    uv run -m scraper_engine.sources.idx.scrape_gapki <date> [filename] [--pages N] [--csv]

    Examples:
    uv run -m scraper_engine.sources.idx.scrape_gapki 20260521
    uv run -m scraper_engine.sources.idx.scrape_gapki 20260521 test_gapki
    uv run -m scraper_engine.sources.idx.scrape_gapki 20260521 test_gapki --pages 3 --csv
    """
    main()