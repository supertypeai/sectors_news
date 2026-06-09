from datetime import datetime, timezone 
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup 

from scraper_engine.base.scraper import Scraper

import argparse 
import logging 
import time 


LOGGER = logging.getLogger(__name__)


class TheEdgeSingapore(Scraper):
    BASE_URL = "https://www.theedgesingapore.com"

    def fetch_article_list(self, url: str) -> list:
        soup = self.fetch_news(url=url)
        
        article_items = soup.select("div[data-testid='teaser-type-1']")
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
            LOGGER.error("[The Edge SG] Failed to parse timestamp '%s': %s", raw_timestamp, error)
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
            title_tag = article_item.select_one("h3.leading-snug a")
            title = title_tag.get_text(strip=True) if title_tag else None
            relative_url = title_tag.get("href") if title_tag else None
            source_url = f"{self.BASE_URL}{relative_url}" if relative_url else None

            if not title or not source_url:
                continue
            
            if article_item.select_one("img[alt='Premium']"):
                LOGGER.info("[The Edge SG] Skipping premium article: %s", title)
                continue

            noscript_tag = article_item.select_one("noscript")
    
            thumbnail_url = None

            if noscript_tag:
                noscript_soup = BeautifulSoup(
                    noscript_tag.decode_contents(), "html.parser"
                )
                img_tag = noscript_soup.find("img")

                if img_tag:
                    raw_src = img_tag.get("src")
                    thumbnail_url = f"{self.BASE_URL}{raw_src}" if raw_src and raw_src.startswith("/") else raw_src

            published_at = self.fetch_article_timestamp(source_url)
            time.sleep(0.3)

            if not published_at:
                LOGGER.info("[The Edge SG] Failed to parse timestamp for %s. Skipping.", source_url)
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
        section_url = f"{self.BASE_URL}/section/news/"
        page_number = 1

        while True:
            page_url = f"{section_url}{page_number}"
        
            article_items = self.fetch_article_list(page_url)

            if not article_items:
                LOGGER.info("[SBR SG] No articles found on page %d, stopping.", page_number)
                break

            articles, reached_older_date = self.parse_articles(article_items, date)

            self.articles.extend(articles)
            LOGGER.info("[SBR SG] Page %d: %d articles collected.", page_number, len(articles))

            if reached_older_date:
                LOGGER.info("[SBR SG] Reached articles older than %s, stopping.", date)
                break

            if num_pages is not None and page_number >= num_pages:
                break

            page_number += 1
            time.sleep(1)

        LOGGER.info("[SBR SG] Total scraped: %d", len(self.articles))
        return self.articles


def main():
    scraper = TheEdgeSingapore()

    parser = argparse.ArgumentParser(description="Script for scraping data from the edge")
    parser.add_argument("date", type=str)
    parser.add_argument("filename", type=str, nargs="?", default="theedge")
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
    uv run -m src.scraper_engine.sources.sgx.scrape_the_edge <date> [filename] [--pages N] [--csv]

    Examples:
    uv run -m src.scraper_engine.sources.sgx.scrape_the_edge 20260427
    uv run -m src.scraper_engine.sources.sgx.scrape_the_edge 20260427 test_scrape_the_edge
    uv run -m src.scraper_engine.sources.sgx.scrape_the_edge 20260427 test_scrape_the_edge --pages 3 --csv
    """
    main()
    
