from datetime import datetime

from scraper_engine.base.scraper import Scraper
from scraper_engine.sources.idx.utils.constant import INDO_TO_ENG

import argparse
import time
import logging 
import re 


LOGGER = logging.getLogger(__name__)


class KompasMoney(Scraper):
    def fetch_article_list(self, url: str) -> list:
        soup = self.fetch_news(url)

        if not soup:
            return []

        return soup.select("div.articleItem")

    def fetch_article_timestamp(self, article_url: str) -> str:
        soup = self.fetch_news(article_url)

        if not soup:
            return None
        
        read_time_tag = soup.select_one("div.read__time")
       
        if not read_time_tag:
            return None

        raw_text = "".join(
            text_node
            for text_node in read_time_tag.strings
            if text_node.strip() and "kompas.com" not in text_node.strip().lower()
        ).strip().strip(",").strip()

        cleaned = self.parse_date(raw_text)
    
        return cleaned

    def parse_date(self, raw_date: str) -> str:
        if not raw_date:
            return None
        
        try:
            cleaned_date = (
                raw_date.replace("WIB", "")
                .replace("WITA", "")
                .replace("WIT", "")
                .strip()
                .strip(",")
                .strip()
            )

            for idn_month, eng_month in INDO_TO_ENG.items(): 
                if idn_month.lower() in cleaned_date.lower():
                    cleaned_date = re.sub(re.escape(idn_month), eng_month, cleaned_date, flags=re.IGNORECASE)
                    break

            parsed_date = datetime.strptime(cleaned_date, "%d %B %Y, %H:%M")
            return parsed_date.strftime("%Y-%m-%d %H:%M:%S")
        
        except ValueError:
            return None
        
    def parse_articles(self, article_items: list) -> list:
        parsed_articles = []

        for article_item in article_items:
            anchor_tag = article_item.select_one("a.article-link")
            source_url = anchor_tag["href"] if anchor_tag else None

            title_tag = article_item.select_one("h2.articleTitle")
            title = title_tag.get_text(strip=True) if title_tag else None

            thumbnail_tag = article_item.select_one("div.articleItem-img img")
            thumbnail_url = thumbnail_tag["src"] if thumbnail_tag else None

            published_at = None
            if source_url:
                published_at = self.fetch_article_timestamp(source_url)
                time.sleep(0.5)

            print(published_at)
            parsed_articles.append({
                "title": title,
                "source": source_url,
                "thumbnail": thumbnail_url,
                "timestamp": published_at,
            })

        return parsed_articles

    def extract_news_pages(self, num_pages: int, date: str):
        base_url = f'https://indeks.kompas.com/?site=money' 
        
        year = date[:4]    
        month = date[4:6] 
        day = date[6:]

        page = 1 

        while True:
            params = f'&date={year}-{month}-{day}&page={page}'
            full_url = base_url + params 
            article_list = self.fetch_article_list(full_url)

            if not article_list:
                LOGGER.info("[Kompas Money] No articles found on page %d, stopping.", page)
                break 

            articles = self.parse_articles(article_list)
            
            self.articles.extend(articles)
            LOGGER.info("[Kompas Money] Page %d: %d articles collected.", page, len(articles))

            if num_pages is not None and page >= num_pages: 
                break
            
            page += 1
            time.sleep(1)

        LOGGER.info("[Kompas Money] Total scraped: %d", len(self.articles))
        return self.articles


def main():
    scraper = KompasMoney()

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
    uv run -m src.scraper_engine.sources.idx.scrape_kompas <date> [filename] [--pages N] [--csv]

    Examples:
    uv run -m src.scraper_engine.sources.idx.scrape_kompas 20260427
    uv run -m src.scraper_engine.sources.idx.scrape_kompas 20260427 test_kompas
    uv run -m src.scraper_engine.sources.idx.scrape_kompas 20260427 test_kompas --pages 3 --csv
    """
    main()
