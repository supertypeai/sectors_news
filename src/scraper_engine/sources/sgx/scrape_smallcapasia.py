from datetime import datetime
from zoneinfo import ZoneInfo

from scraper_engine.base.scraper import Scraper

import argparse
import logging
import time


LOGGER = logging.getLogger(__name__)


class SmallCapAsia(Scraper):
    BASE_URL = "https://www.smallcapasia.com"
    SINGAPORE_MARKET_URL = f"{BASE_URL}/market/singapore/"
    SINGAPORE_TIMEZONE = ZoneInfo("Asia/Singapore")

    def fetch_article_list(self, url: str) -> list:
        soup = self.fetch_news(url)
        listing_container = soup.select_one(".elementor-element-7fff712.main-loop")

        if not listing_container:
            LOGGER.warning("[SmallCapAsia] Listing container not found: %s", url)
            return []

        return listing_container.select(".e-loop-item")

    def parse_timestamp(self, raw_timestamp: str) -> datetime | None:
        if not raw_timestamp:
            return None

        try:
            return datetime.strptime(
                raw_timestamp.strip(),
                "%B %d, %Y",
            ).replace(tzinfo=self.SINGAPORE_TIMEZONE)

        except ValueError as error:
            LOGGER.warning(
                "[SmallCapAsia] Failed to parse timestamp '%s': %s",
                raw_timestamp,
                error,
            )
            return None

    def fetch_article_content(self, article_url: str) -> str | None:
        soup = self.fetch_news(article_url)
        content_container = soup.select_one(".elementor-widget-theme-post-content")

        if not content_container:
            LOGGER.warning(
                "[SmallCapAsia] Article content not found: %s",
                article_url,
            )
            return None

        article_body = content_container.get_text(separator="\n", strip=True)

        return article_body or None

    def parse_articles(
        self,
        article_items: list,
        target_date: str,
    ) -> tuple[list, bool]:
        parsed_articles = []
        reached_older_date = False

        target_datetime = datetime.strptime(
            target_date,
            "%Y%m%d",
        ).replace(tzinfo=self.SINGAPORE_TIMEZONE)

        for article_item in article_items:
            title_tag = article_item.select_one(
                ".elementor-widget-theme-post-title a[href]"
            )

            date_tag = article_item.select_one(
                ".elementor-widget-post-info time"
            )

            title = title_tag.get_text(" ", strip=True) if title_tag else None

            article_url = title_tag.get("href") if title_tag else None

            published_at = self.parse_timestamp(
                date_tag.get_text(" ", strip=True) if date_tag else None
            )

            if not title or not article_url or not published_at:
                LOGGER.warning("[SmallCapAsia] Incomplete listing card; skipping")
                continue

            if published_at < target_datetime:
                reached_older_date = True
                break

            image_tag = article_item.select_one(
                ".elementor-widget-theme-post-featured-image img"
            )

            thumbnail_url = image_tag.get("src") if image_tag else None
            article_body = self.fetch_article_content(article_url)

            parsed_articles.append({
                "title": title,
                "source": article_url,
                "thumbnail": thumbnail_url,
                "timestamp": published_at.strftime("%Y-%m-%d %H:%M:%S"),
                "article": article_body,
            })

            time.sleep(0.3)

        return parsed_articles, reached_older_date

    def extract_news_pages(self, num_pages: int | None, date: str) -> list:
        page_number = 1

        while True:
            page_url = (
                f"{self.SINGAPORE_MARKET_URL}"
                f"?e-page-7fff712={page_number}"
            )
            article_items = self.fetch_article_list(page_url)

            if not article_items:
                LOGGER.info(
                    "[SmallCapAsia] No articles found on page %d, stopping.",
                    page_number,
                )
                break

            articles, reached_older_date = self.parse_articles(article_items, date)

            self.articles.extend(articles)

            LOGGER.info(
                "[SmallCapAsia] Page %d: %d articles collected.",
                page_number,
                len(articles),
            )

            if reached_older_date:
                LOGGER.info(
                    "[SmallCapAsia] Reached articles older than %s, stopping.",
                    date,
                )
                break

            if num_pages is not None and page_number >= num_pages:
                break

            page_number += 1
            time.sleep(1)

        LOGGER.info("[SmallCapAsia] Total scraped: %d", len(self.articles))

        return self.articles


def main():
    scraper = SmallCapAsia()

    parser = argparse.ArgumentParser(
        description="Scrape SmallCapAsia Singapore market articles"
    )
    parser.add_argument("date", type=str)
    parser.add_argument(
        "filename",
        type=str,
        nargs="?",
        default="smallcapasia",
    )
    parser.add_argument(
        "--pages",
        type=int,
        default=None,
        help="Number of pages to scrape (default: until the target date)",
    )
    parser.add_argument("--csv", action="store_true")

    args = parser.parse_args()
    scraper.extract_news_pages(args.pages, args.date)
    scraper.write_json(scraper.articles, args.filename)

    if args.csv:
        scraper.write_csv(scraper.articles, args.filename)


if __name__ == "__main__":
    main()
