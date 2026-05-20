from datetime import datetime
from bs4 import BeautifulSoup 

from scraper_engine.base.scraper import Scraper
from scraper_engine.sources.idx.utils.constant import INDONESIAN_MONTHS

import argparse
import time
import logging 


LOGGER = logging.getLogger(__name__)


class InvestorID(Scraper):
    def fetch_article_list(self, url: str) -> list:
        raw_html_content = self.fetch_news_with_proxy(url)

        if not raw_html_content:
            LOGGER.info("[Investor ID] [FAIL] Failed to fetch HTML or timed out for %s", url)
            return []

        soup = BeautifulSoup(raw_html_content, "html.parser")
        return soup.find_all("div", class_="row mb-4 position-relative")

    def fetch_article_timestamp(self, article_url: str) -> str:
        raw_html_content = self.fetch_news_with_proxy(article_url)
        soup = BeautifulSoup(raw_html_content, "html.parser")

        date_tag = soup.select_one("div.col.small.pt-1 span.text-muted")

        if not date_tag:
            return None

        return self.parse_timestamp(date_tag.get_text(strip=True))

    def parse_timestamp(self, raw_timestamp: str) -> str:
        if not raw_timestamp:
            return None

        try:
            cleaned = raw_timestamp.strip()

            for timezone_label in ["WIB", "WITA", "WIT"]:
                cleaned = cleaned.replace(timezone_label, "")

            date_parts = cleaned.split("|")

            if len(date_parts) != 2:
                return None

            date_part = date_parts[0].strip()
            time_part = date_parts[1].strip()

            parts = date_part.split()
            day = int(parts[0])
            month = INDONESIAN_MONTHS.get(parts[1])
            year = int(parts[2])

            if not month:
                return None

            hour, minute = time_part.split(":")
            parsed_date = datetime(year, month, day, int(hour), int(minute))
            return parsed_date.strftime("%Y-%m-%d %H:%M:%S")

        except (ValueError, IndexError, AttributeError) as error:
            LOGGER.error("[Investor ID] Error parsing date '%s': %s", raw_timestamp, error)
            return None

    def parse_articles(self, article_items: list, target_date: str) -> tuple[list, bool]:
        parsed_articles = []
        seen_urls = set()
        reached_older_date = False

        target_datetime = datetime(
            int(target_date[:4]),
            int(target_date[4:6]),
            int(target_date[6:]),
        )

        for article_item in article_items:
            anchor_tag = article_item.find("a", class_="stretched-link")

            if not anchor_tag:
                continue

            relative_url = anchor_tag.get("href")
            source_url = f"https://investor.id{relative_url}" if relative_url and relative_url.startswith("/") else relative_url

            if not source_url or source_url in seen_urls:
                continue

            title_tag = article_item.find("h4", class_="my-3 text-truncate-2-lines")
            title = title_tag.get_text(strip=True) if title_tag else None

            thumbnail_tag = article_item.select_one("div.col-4 img.lazy")
            thumbnail_url = thumbnail_tag["src"] if thumbnail_tag else None

            raw_date = ""
            date_span = article_item.find("span", class_="text-muted small")
            
            if date_span:
                raw_date = date_span.get_text(strip=True)

            published_at = None

            if "menit yang lalu" in raw_date or "jam yang lalu" in raw_date or "hari yang lalu" in raw_date:
                published_at = self.fetch_article_timestamp(source_url)
                time.sleep(0.5)

            else:
                published_at = self.parse_timestamp(raw_date)

            if not published_at:
                LOGGER.info("[Investor ID] Failed to parse date for url: %s. Skipping.", source_url)
                continue

            article_datetime = datetime.strptime(published_at[:10], "%Y-%m-%d")

            if article_datetime < target_datetime:
                reached_older_date = True
                break

            if not title:
                continue

            seen_urls.add(source_url)
            parsed_articles.append({
                "title": title,
                "source": source_url,
                "thumbnail": thumbnail_url,
                "timestamp": published_at,
            })

        return parsed_articles, reached_older_date

    def extract_news_pages(self, num_pages: int, date: str) -> list:
        base_urls = [
            "https://investor.id/stock/indeks/",
            "https://investor.id/corporate-action/indeks/",
        ]

        for base_url in base_urls:
            page_number = 1 

            while True:
                page_url = f'{base_url}{page_number}'

                article_items = self.fetch_article_list(page_url)
                
                if not article_items:
                    LOGGER.info("[Investor ID] No articles found on page %d, stopping.", page_number)
                    break

                articles, reached_older_date = self.parse_articles(article_items, date)

                self.articles.extend(articles)
                LOGGER.info("[Investor ID] Page %d: %d articles collected.", page_number, len(articles))

                if reached_older_date:
                    LOGGER.info("[Investor ID] Reached articles older than %s, stopping.", date)
                    break

                if num_pages is not None and page_number >= num_pages:
                    break

                page_number += 1
                time.sleep(1)

        LOGGER.info("[Investor ID] Total scraped: %d", len(self.articles))
        return self.articles


def main():
    scraper = InvestorID()

    parser = argparse.ArgumentParser(description="Script for scraping data from Investor ID")
    parser.add_argument("date", type=str)
    parser.add_argument("filename", type=str, nargs="?", default="investorid")
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
    uv run -m src.scraper_engine.sources.idx.scrape_investor_id <date> [filename] [--pages N] [--csv]

    Examples:
    uv run -m src.scraper_engine.sources.idx.scrape_investor_id 20260427
    uv run -m src.scraper_engine.sources.idx.scrape_investor_id 20260427 test_investor_id
    uv run -m src.scraper_engine.sources.idx.scrape_investor_id 20260427 test_investor_id --pages 3 --csv
    '''
    main()

