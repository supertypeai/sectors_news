from datetime import datetime 
from urllib.parse import urljoin

from scraper_engine.base.scraper import Scraper

import argparse
import time
import logging


LOGGER = logging.getLogger(__name__)


class AntaraNewsScraper(Scraper):
    def extract_news(self, url: str):
        soup = self.fetch_news(url)

        article_cards = soup.select("div.card__post.card__post__transition")
        
        for card in article_cards:
            title_tag = card.select_one("h2.h5 a")
            title = title_tag.get_text(strip=True)

            source = title_tag.get('href')
            
            source = urljoin(url, source)

            timestamp = self.get_article_timestamp(source)

            final_date = self.standardize_date(timestamp)

            if not final_date:
                print(f"[Antara News] Failed parse date for url: {source} Skipping")
                continue 

            self.articles.append({
                'title': title or None,
                'source': source,
                'timestamp': final_date
            })

        LOGGER.info(f'total scraped source of antara news: {len(self.articles)}')
        return self.articles

    def standardize_date(self, date: str) -> str:
        idn_months = {
            "Januari": "01", "Februari": "02", "Maret": "03",
            "April": "04", "Mei": "05", "Juni": "06",
            "Juli": "07", "Agustus": "08", "September": "09",
            "Oktober": "10", "November": "11", "Desember": "12"
        }
        
        try:
            date_without_day = date.split(", ", 1)[-1]
            date_clean = date_without_day.split(" WIB")[0].strip()

            for indonesian_month, month_number in idn_months.items():
                if indonesian_month in date_clean:
                    date_clean = date_clean.replace(indonesian_month, month_number)
                    break

            timestamp_dt = datetime.strptime(date_clean, "%d %m %Y %H:%M")
            return timestamp_dt.strftime("%Y-%m-%d %H:%M:%S")

        except ValueError as error:
            LOGGER.error(f"Error parsing date antara news {date}: {error}")
            return None

    def get_article_timestamp(self, article_url: str) -> str:
        soup = self.fetch_news(article_url)

        if not soup:
            return None

        # Get article date
        date_span = soup.select_one("div.wrap__article-detail-info span")

        if date_span:
            return date_span.get_text(strip=True)
        
        return None

    def extract_news_pages(self, num_pages: int):
        for index in range(1, num_pages+1):
            self.extract_news(self.get_page(index))
            time.sleep(1)
        return self.articles
   
    def get_page(self, page_num: int) -> str:
        # changed to ekonomi bursa category from /business-investment
        return f"https://www.antaranews.com/ekonomi/bursa/{page_num}"
    

def main():
  scraper = AntaraNewsScraper()

  parser = argparse.ArgumentParser(description="Script for scraping data from antaranews")
  parser.add_argument("page_number", type=int, default=1)
  parser.add_argument("filename", type=str, default="anataranews")
  parser.add_argument("--csv", action='store_true', help="Flag to indicate write to csv file")

  args = parser.parse_args()

  num_page = args.page_number

  scraper.extract_news_pages(num_page)
    
  scraper.write_json(scraper.articles, args.filename)

  if args.csv:
     scraper.write_csv(scraper.articles, args.filename)


if __name__ == "__main__":
  '''
  How to run:
  uv run -m src.scraper_engine.sources.idx.scrape_antaranews <page_number> <filename_saved> <--csv (optional)>
  '''
  main()