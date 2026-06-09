from datetime import datetime, timezone 
from zoneinfo import ZoneInfo

from scraper_engine.base.scraper import SeleniumScraper

import argparse 
import logging 
import time 


LOGGER = logging.getLogger(__name__)


class EdgeProp(SeleniumScraper):
    BASE_URL = "https://www.edgeprop.sg"

    def fetch_article_list(self, url: str) -> list:
        soup = self.fetch_news_with_selenium(url, wait_selector="div.article-description")

        with open('output.html', 'w') as file: 
            file.write(soup.prettify())

        if not soup:
            LOGGER.warning("[EdgeProp SG] Empty soup for %s", url)
            return []

        LOGGER.debug("[EdgeProp SG] Soup preview: %s", str(soup)[:300])

        article_items = soup.select("div.main-container")

        if not article_items:
            LOGGER.warning("[EdgeProp SG] No article items found. Soup preview: %s", str(soup)[:300])

        return article_items if article_items else []

    def fetch_article_timestamp(self, article_url: str) -> str:
        soup = self.fetch_news(url=article_url)

        time_tag = soup.select_one("time[datetime]")

        if not time_tag:
            return None

        return self.parse_timestamp(time_tag.get("datetime"))

    def parse_timestamp(self, raw_timestamp: str) -> str:
        if not raw_timestamp:
            return None

        try:
            dt = datetime.fromisoformat(raw_timestamp)

            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)

            return dt.astimezone(ZoneInfo("Asia/Singapore"))

        except (ValueError, AttributeError) as error:
            LOGGER.error("[EdgeProp SG] Failed to parse timestamp '%s': %s", raw_timestamp, error)
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
            anchor_tag = article_item.select_one("div.article-container.hyperlink a")
 
            if not anchor_tag:
                continue
 
            title_tag = anchor_tag.select_one("div.article-description")
            title = title_tag.get_text(strip=True) if title_tag else None
            relative_url = anchor_tag.get("href")
            source_url = f"{self.BASE_URL}{relative_url}" if relative_url and relative_url.startswith("/") else relative_url
 
            if not title or not source_url:
                continue
 
            if article_item.select_one("img[alt='Premium']"):
                LOGGER.info("[EdgeProp SG] Skipping premium article: %s", title)
                continue
 
            thumbnail_tag = article_item.select_one("div.left-container a img[src]")
            thumbnail_url = thumbnail_tag.get("src") if thumbnail_tag else None
            
            published_at = self.fetch_article_timestamp(source_url)
            time.sleep(0.3)
 
            if not published_at:
                LOGGER.info("[EdgeProp SG] Failed to parse timestamp for %s. Skipping.", source_url)
                continue
           
            if published_at < target_datetime:
                reached_older_date = True
                break
 
            parsed_articles.append({
                "title": title,
                "source": source_url,
                "thumbnail": thumbnail_url,
                "timestamp": published_at.strftime("%Y-%m-%d %H:%M:%S"),
            })
 
        return parsed_articles, reached_older_date

    def extract_news_pages(self, num_pages: int, date: str) -> list:
        page_number = 1
 
        while True:
            section_url = f'/property-news-search?combine=&field_tags_tid=&page={page_number}&page_size=20&sort_by=posted_desc&category='
            page_url = f"{self.BASE_URL}{section_url}"
 
            article_items = self.fetch_article_list(page_url)
 
            if not article_items:
                LOGGER.info("[EdgeProp SG] No articles found on page %d, stopping.", page_number)
                break
 
            articles, reached_older_date = self.parse_articles(article_items, date)
 
            self.articles.extend(articles)
            LOGGER.info("[EdgeProp SG] Page %d: %d articles collected.", page_number, len(articles))
 
            if reached_older_date:
                LOGGER.info("[EdgeProp SG] Reached articles older than %s, stopping.", date)
                break
 
            if num_pages is not None and page_number >= num_pages:
                break
 
            page_number += 1
            time.sleep(1)
 
        LOGGER.info("[EdgeProp SG] Total scraped: %d", len(self.articles))
        return self.articles


def main():
    scraper = EdgeProp()

    parser = argparse.ArgumentParser(description="Script for scraping data from edgeprop")
    parser.add_argument("date", type=str)
    parser.add_argument("filename", type=str, nargs="?", default="edgeprop")
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
    uv run -m src.scraper_engine.sources.sgx.scrape_edgeprop <date> [filename] [--pages N] [--csv]

    Examples:
    uv run -m src.scraper_engine.sources.sgx.scrape_edgeprop 20260427
    uv run -m src.scraper_engine.sources.sgx.scrape_edgeprop 20260608 test_scrape_edgeprop
    uv run -m src.scraper_engine.sources.sgx.scrape_edgeprop 20260427 test_scrape_edgeprop --pages 3 --csv
    """
    main()
    
