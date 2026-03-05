from datetime import datetime, timedelta
from bs4 import BeautifulSoup 

from scraper_engine.base.scraper import SeleniumScraper

import argparse
import time
import re 
import logging 
import requests 


LOGGER = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0",
}


class InvestorID(SeleniumScraper):
    def extract_news(self, url):
        soup = self.fetch_news_with_selenium(url)
        seen_urls = set()

        article_containers = soup.find_all('div', class_='row mb-4 position-relative')

        for article_container in article_containers:
            link_element = article_container.find('a', class_='stretched-link')
            
            if not link_element:
                continue

            article_url = link_element.get('href')
            
            # Convert relative path to absolute URL
            if article_url and article_url.startswith('/'):
                article_url = f"https://investor.id{article_url}"

            if not article_url or article_url in seen_urls:
                continue

            title_element = article_container.find('h4', class_='my-3 text-truncate-2-lines')
            article_title = title_element.get_text(strip=True) if title_element else ""

            publish_time = ""

            if article_url:
                publish_time = self.fetch_exact_timestamp(article_url)
                print(f'time article: {publish_time}')

            if not publish_time:
                time_element = article_container.find('span', class_='text-muted small')

                if time_element:
                    relative_time_raw = time_element.get_text(strip=True)
                    publish_time = self.calculate_relative_timestamp(relative_time_raw)
                    print(f'time relative: {publish_time}')

            if not publish_time:
                LOGGER.info(f"Failed to extract publish time for url: {article_url}. Skipping.")
                continue

            seen_urls.add(article_url)

            if article_title and article_url:
                extracted_article = {
                    'title': article_title,
                    'source': article_url,
                    'timestamp': publish_time
                }
                
                self.articles.append(extracted_article)

        LOGGER.info(f'total scraped source of investor id: {len(self.articles)}')
        return self.articles

    def fetch_exact_timestamp(self, article_url: str) -> str:
        session = requests.Session()
        response = session.get(article_url, headers=HEADERS, timeout=15)
        response_text = response.text[:500]

        data_layer_match = re.search(r'"detail_published_date"\s*:\s*"([^"]+)"', response_text)

        if data_layer_match:
            raw_time_string = data_layer_match.group(1)
            
            # Parses format: "Kamis, 5 Maret 2026 | 08:45 WIB"
            time_match = re.search(r'(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})\s*\|\s*(\d{2}:\d{2})', raw_time_string)
            
            if time_match:
                extracted_day = time_match.group(1)
                extracted_month_string = time_match.group(2)
                extracted_year = time_match.group(3)
                extracted_time_string = time_match.group(4)
                
                indonesian_months_mapping = {
                    "Januari": "01", "Februari": "02", "Maret": "03", "April": "04", 
                    "Mei": "05", "Juni": "06", "Juli": "07", "Agustus": "08", 
                    "September": "09", "Oktober": "10", "November": "11", "Desember": "12"
                }
                
                month_number = indonesian_months_mapping.get(extracted_month_string)
                
                if month_number:
                    # Construct the final strict format "%Y-%m-%d %H:%M:%S"
                    formatted_timestamp = f"{extracted_year}-{month_number}-{extracted_day.zfill(2)} {extracted_time_string}:00"
                    return formatted_timestamp
                    
        return ""

    def calculate_relative_timestamp(self, relative_time_string: str) -> str:
        current_time = datetime.now()
        
        minutes_match = re.search(r'(\d+)\s+menit', relative_time_string)
        if minutes_match:
            extracted_minutes = int(minutes_match.group(1))
            calculated_time = current_time - timedelta(minutes=extracted_minutes)
            return calculated_time.strftime("%Y-%m-%d %H:%M:%S")
            
        hours_match = re.search(r'(\d+)\s+jam', relative_time_string)
        if hours_match:
            extracted_hours = int(hours_match.group(1))
            calculated_time = current_time - timedelta(hours=extracted_hours)
            return calculated_time.strftime("%Y-%m-%d %H:00:00")

        days_match = re.search(r'(\d+)\s+hari', relative_time_string)
        if days_match:
            extracted_days = int(days_match.group(1))
            calculated_time = current_time - timedelta(days=extracted_days)
            return calculated_time.strftime("%Y-%m-%d 00:00:00")
            
        return ""
    
    def extract_news_pages(self, num_pages):
        for index in range(1, num_pages+1):
            self.extract_news(self.get_page(index))
            time.sleep(1)
        return self.articles
   
    def get_page(self, page_num) -> str:
        return f"https://investor.id/stock/indeks/{page_num}"  
    

def main():
  scraper = InvestorID()

  parser = argparse.ArgumentParser(description="Script for scraping data from fianncialbisnis")
  parser.add_argument("page_number", type=int, default=1)
  parser.add_argument("filename", type=str, default="fianncialbisnis")
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
    uv run -m src.scraper_engine.sources.idx.scrape_investor_id <page_number> <filename_saved> <--csv (optional)>
    '''
    main()

   