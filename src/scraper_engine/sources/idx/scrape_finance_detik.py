from datetime import datetime
from pathlib import Path 

from scraper_engine.base.scraper import Scraper
from scraper_engine.sources.idx.utils.constant import INDONESIAN_MONTHS

import argparse
import time
import logging 


LOGGER = logging.getLogger(__name__)


class FinanceDetik(Scraper):
    def fetch_article_list(self, url: str):
        soup = self.fetch_news(url)

        article_items = soup.find_all("article", class_="list-content__item")
        
        return article_items 
    
    def parse_articles(self, article_items):
        parsed_articles = []

        for article_item in article_items:
            title_tag = article_item.find("h3", class_="media__title")
            title_link = title_tag.find("a") if title_tag else None

            title = title_link.get_text(strip=True) if title_link else None
            source_url = title_link["href"] if title_link else None

            thumbnail_tag = article_item.find("div", class_="media__image")
            thumbnail_img = thumbnail_tag.find("img") if thumbnail_tag else None
            thumbnail_url = thumbnail_img["src"] if thumbnail_img else None

            date_tag = article_item.find("div", class_="media__date")
            date_span = date_tag.find("span") if date_tag else None
            raw_timestamp = date_span["title"] if date_span else None
            published_at = self.parse_timestamp(raw_timestamp) 

            parsed_articles.append({
                "title": title,
                "source": source_url,
                "thumbnail": thumbnail_url,
                'timestamp': published_at
            })

        return parsed_articles
    
    def parse_timestamp(self, raw_timestamp: str) -> str:
        if not raw_timestamp:
            return None
        
        try:
            without_day = raw_timestamp.split(", ", 1)[-1]
            cleaned = without_day.replace("WIB", "").replace("WITA", "").replace("WIT", "").strip()

            parts = cleaned.split()

            day = int(parts[0])
            month = INDONESIAN_MONTHS.get(parts[1])
            year = int(parts[2])
            hour, minute = parts[3].split(":")

            if not month:
                return None

            parsed_date = datetime(year, month, day, int(hour), int(minute))
            return parsed_date.strftime("%Y-%m-%d %H:%M:%S")
        
        except (ValueError, IndexError, AttributeError):
            return None
        
    def extract_news_pages(self, num_pages: int, date: str):
        base_url = 'https://finance.detik.com/bursa-dan-valas/indeks?' 
        
        year = date[:4]    
        month = date[4:6] 
        day = date[6:]

        page = 1 
        
        while True:
            params = f'date={month}%2F{day}%2F{year}&page={page}'
            page_url = base_url + params 

            article_list = self.fetch_article_list(page_url)
            
            if not article_list: 
                LOGGER.info("[Finance Detik] No articles found on page %d, stopping.", page)
                break

            articles = self.parse_articles(article_list)

            self.articles.extend(articles)
            LOGGER.info("[Finance Detik] Page %d: %d articles collected.", page, len(articles))

            if num_pages is not None and page >= num_pages: 
                break
            
            page += 1
            time.sleep(1)

        LOGGER.info("[Finance Detik] Total scraped: %d", len(self.articles))
        return self.articles
   
  
def main():
    scraper = FinanceDetik()

    parser = argparse.ArgumentParser(description="Script for scraping data from finance detik")
    parser.add_argument("date", type=str)
    parser.add_argument("filename", type=str, nargs="?", default="financedetik")
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
    uv run -m src.scraper_engine.sources.idx.scrape_finance_detik <date> [filename] [--pages N] [--csv]

    Examples:
    uv run -m src.scraper_engine.sources.idx.scrape_finance_detik 20260427
    uv run -m src.scraper_engine.sources.idx.scrape_finance_detik 20260427 test_kompas
    uv run -m src.scraper_engine.sources.idx.scrape_finance_detik 20260427 test_kompas --pages 3 --csv
    """
    main()

