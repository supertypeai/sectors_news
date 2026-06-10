from datetime import datetime, timezone 
from zoneinfo import ZoneInfo

from scraper_engine.base.scraper import Scraper

import argparse 
import logging 
import time 


LOGGER = logging.getLogger(__name__)


class SBRSG(Scraper):
    def fetch_article_list(self, url: str) -> list:
        soup = self.fetch_news(url=url)

        taxonomy_view = soup.select_one("div.view-id-taxonomy_term")

        if not taxonomy_view:
            return []

        view_content = taxonomy_view.select_one("div.view-content")
    
        if not view_content:
            return []

        return view_content.select("div.item--large, div.item")

    def fetch_article_timestamp(self, article_url: str) -> str:
        soup = self.fetch_news(url=article_url)

        time_tag = soup.select_one("time[pubdate][datetime]")

        if not time_tag:
            return None

        return self.parse_timestamp(time_tag.get("datetime")) 

    def parse_timestamp(self, raw_timestamp: str) -> str:
        if not raw_timestamp:
            return None

        try:
            dt = datetime.fromisoformat(raw_timestamp)
           
            dt_utc = dt.replace(tzinfo=timezone.utc)
            return dt_utc.astimezone(ZoneInfo("Asia/Singapore"))

        except (ValueError, AttributeError) as error:
            LOGGER.error("[SBRSG] Failed to parse timestamp '%s': %s", raw_timestamp, error)
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
            title_tag = article_item.select_one("h2.item__title a.text-default")
            title = title_tag.get_text(strip=True) if title_tag else None
            source_url = title_tag.get("href") if title_tag else None

            if 'daily markets briefing' in title.lower():
                continue  

            if not title or not source_url:
                continue

            thumbnail_tag = article_item.select_one("img.progressivePlain-img")
            thumbnail_url = thumbnail_tag.get("src") if thumbnail_tag else None

            published_at = self.fetch_article_timestamp(source_url)
            time.sleep(0.5)

            if not published_at:
                LOGGER.info("[SBR SG] Failed to parse timestamp for %s. Skipping.", source_url)
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
        base_urls = [
            "https://sbr.com.sg/stocks",
            'https://sbr.com.sg/markets-investing',
            'https://sbr.com.sg/economy',
            'https://sbr.com.sg/markets',
            'https://sbr.com.sg/healthcare',
            'https://sbr.com.sg/financial-services',
            'https://sbr.com.sg/transport-logistics',
            'https://sbr.com.sg/residential-property'
        ]

        page_number = 0

        for base_url in base_urls:
            while True:
                page_url = f"{base_url}?page={page_number}"
            
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
    scraper = SBRSG()

    parser = argparse.ArgumentParser(description="Script for scraping data from sbr.com.sg")
    parser.add_argument("date", type=str)
    parser.add_argument("filename", type=str, nargs="?", default="sbrsg")
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
    uv run -m src.scraper_engine.sources.sgx.scrape_sbr_sg <date> [filename] [--pages N] [--csv]

    Examples:
    uv run -m src.scraper_engine.sources.sgx.scrape_sbr_sg 20260427
    uv run -m src.scraper_engine.sources.sgx.scrape_sbr_sg 20260427 test_scrape_sbr_sg
    uv run -m src.scraper_engine.sources.sgx.scrape_sbr_sg 20260427 test_scrape_sbr_sg --pages 3 --csv
    """
    main()
    
