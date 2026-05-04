from datetime import datetime

from scraper_engine.base import Scraper

import argparse
import logging
import time 


LOGGER = logging.getLogger(__name__)


class AbafScraper(Scraper):
    def fetch_article_list(self, url: str) -> list:
        soup = self.fetch_news(url)

        if not soup:
            LOGGER.info("[ABAF] [FAIL] Failed to fetch HTML or timed out for %s", url)
            return []

        article_items = soup.find_all("div", class_="item with-border-bottom")
        headline = soup.find("div", class_="item--large with-border-bottom")

        if headline:
            article_items = [headline] + list(article_items)

        return article_items

    def fetch_article_timestamp(self, article_url: str) -> str:
        soup = self.fetch_news(article_url)

        if not soup:
            return None

        time_tag = soup.select_one("div.nf-value time[datetime]")

        if not time_tag:
            return None

        raw_datetime = time_tag.get("datetime")

        try:
            dt_obj = datetime.fromisoformat(raw_datetime)
            return dt_obj.strftime("%Y-%m-%d %H:%M:%S")
        
        except (ValueError, TypeError):
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
            anchor_tag = article_item.select_one("h2 a") or article_item.select_one("a")

            if not anchor_tag:
                continue

            source_url = anchor_tag.get("href")
            title = anchor_tag.get_text(strip=True)

            if not source_url or not title:
                continue

            thumbnail_tag = article_item.select_one("img.progressivePlain-img")
            thumbnail_url = thumbnail_tag["src"] if thumbnail_tag else None

            published_at = self.fetch_article_timestamp(source_url)

            if not published_at:
                LOGGER.info("[ABAF] Failed to parse date for url: %s. Skipping.", source_url)
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
            page_url = f"https://asianbankingandfinance.net/market/indonesia?page={page_number}"
            print(page_url)

            article_items = self.fetch_article_list(page_url)

            if not article_items:
                LOGGER.info("[ABAF] No articles found on page %d, stopping.", page_number)
                break

            articles, reached_older_date = self.parse_articles(article_items, date)

            self.articles.extend(articles)
            LOGGER.info("[ABAF] Page %d: %d articles collected.", page_number, len(articles))

            if reached_older_date:
                LOGGER.info("[ABAF] Reached articles older than %s, stopping.", date)
                break

            if num_pages is not None and page_number >= num_pages:
                break

            page_number += 1
            time.sleep(1)

        LOGGER.info("[ABAF] Total scraped: %d", len(self.articles))
        return self.articles


def main():
    scraper = AbafScraper()

    parser = argparse.ArgumentParser(description="Script for scraping data from Asian Banking and Finance")
    parser.add_argument("date", type=str)
    parser.add_argument("filename", type=str, nargs="?", default="abafarticles")
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
    uv run -m src.scraper_engine.sources.idx.scrape_abaf <date> [filename] [--pages N] [--csv]

    Examples:
    uv run -m src.scraper_engine.sources.idx.scrape_abaf 20260427
    uv run -m src.scraper_engine.sources.idx.scrape_abaf 20260430 test_abaf
    uv run -m src.scraper_engine.sources.idx.scrape_abaf 20260427 test_abaf --pages 3 --csv
    '''
    main()
