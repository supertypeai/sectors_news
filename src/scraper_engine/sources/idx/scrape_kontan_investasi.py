from datetime import datetime
from bs4 import BeautifulSoup

from scraper_engine.base.scraper import Scraper
from scraper_engine.sources.utils.constant import INDONESIAN_MONTHS
from scraper_engine.sources.utils.time_parser import parse_relative_time

import argparse
import logging
import time 


LOGGER = logging.getLogger(__name__)


class KontanInvestasi(Scraper):
    def fetch_article_list(self, url: str) -> list:
        raw_html_content = self.fetch_news_with_proxy(url)

        if not raw_html_content:
            return []

        soup = BeautifulSoup(raw_html_content, "html.parser")
        return soup.select("div.list-berita ul li")

    def parse_timestamp(self, raw_timestamp: str) -> str:
        if not raw_timestamp:
            return None

        try:
            cleaned = raw_timestamp.strip().lstrip("|").strip()

            if "," in cleaned:
                cleaned = cleaned.split(", ", 1)[-1]

            for timezone_label in ["WIB", "WITA", "WIT"]:
                cleaned = cleaned.replace(timezone_label, "")

            cleaned = cleaned.replace("/", "").strip()

            parts = cleaned.split()
            day = int(parts[0])
            month = INDONESIAN_MONTHS.get(parts[1])
            year = int(parts[2])

            if not month:
                return None

            if len(parts) >= 4:
                hour, minute = parts[3].split(":")
                parsed_date = datetime(year, month, day, int(hour), int(minute))

            else:
                parsed_date = datetime(year, month, day, 23, 59, 59)

            return parsed_date.strftime("%Y-%m-%d %H:%M:%S")

        except (ValueError, IndexError, AttributeError):
            return None

    def parse_articles(self, article_items: list) -> list:
        parsed_articles = []

        for article_item in article_items:
            anchor_tag = article_item.select_one("a")
            source_url = anchor_tag["href"] if anchor_tag else None

            title_tag = article_item.select_one("div.sp-hl h1 a")
            title = title_tag.get_text(strip=True) if title_tag else None

            thumbnail_tag = article_item.select_one("div.pic img")
            thumbnail_url = thumbnail_tag["data-src"] if thumbnail_tag else None

            raw_date = ""
            date_tag = article_item.select_one("span.font-gray")
            if date_tag:
                raw_date = date_tag.get_text(strip=True)

            published_at = parse_relative_time(raw_date) or self.parse_timestamp(raw_date)

            if not published_at:
                LOGGER.warning("[Kontan Investasi] Could not parse timestamp '%s' for %s", raw_date, source_url)

            parsed_articles.append({
                "title": title,
                "source": source_url,
                "thumbnail": thumbnail_url,
                "timestamp": published_at,
            })

        return parsed_articles

    def extract_news_pages(self, num_pages: int, date: str) -> list:
        base_url = "https://www.kontan.co.id/search/indeks"

        year = date[:4]
        month = date[4:6]
        day = date[6:]

        base_params = f"kanal=investasi&tanggal={day}&bulan={month}&tahun={year}&pos=indeks"
        page_number = 1

        while True:
            if page_number == 1:
                full_url = f"{base_url}?{base_params}"
            else:
                per_page_offset = page_number * 10
                full_url = f"{base_url}?{base_params}&per_page={per_page_offset}"

            article_items = self.fetch_article_list(full_url)

            if not article_items:
                LOGGER.info("[Kontan Investasi] No articles found on page %d, stopping.", page_number)
                break

            articles = self.parse_articles(article_items)

            self.articles.extend(articles)
            LOGGER.info("[Kontan Investasi] Page %d: %d articles collected.", page_number, len(articles))

            if num_pages is not None and page_number >= num_pages:
                break

            page_number += 1
            time.sleep(1)

        LOGGER.info("[Kontan Investasi] Total scraped: %d", len(self.articles))
        return self.articles


def main():
    scraper = KontanInvestasi()

    parser = argparse.ArgumentParser(description="Script for scraping data from Kompas Money")
    parser.add_argument("date", type=str)
    parser.add_argument("filename", type=str, nargs="?", default="kompasmoney")
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
    uv run -m src.scraper_engine.sources.idx.scrape_kontan_investasi <date> [filename] [--pages N] [--csv]

    Examples:
    uv run -m src.scraper_engine.sources.idx.scrape_kontan_investasi 20260427
    uv run -m src.scraper_engine.sources.idx.scrape_kontan_investasi 20260427 test_kontan_investasi
    uv run -m src.scraper_engine.sources.idx.scrape_kontan_investasi 20260427 test_kompas --pages 3 --csv
    """
    main()
