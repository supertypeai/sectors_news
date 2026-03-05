from datetime import datetime, timedelta
from bs4 import BeautifulSoup

from scraper_engine.base.scraper import SeleniumScraper

import argparse
import time
import re 
import logging 
import requests


LOGGER = logging.getLogger(__name__)


class BloombergTechnoz(SeleniumScraper):
    def extract_news(self, url: str, limit: int = 10):
        soup = self.fetch_news_with_selenium(url)
        seen = set()

        article_containers = soup.find_all('div', class_='card-box')

        for article_container in article_containers:
            link_element = article_container.find('a')

            if not link_element:
                continue

            article_url = link_element.get('href')

            if article_url in seen:
                continue

            title_element = article_container.find(['h2', 'h5', 'h6'], class_='title')
            article_title = title_element.get_text(strip=True) if title_element else ""

            meta_element = article_container.find('h6', class_='title fw4 cl-blue')
            
            if meta_element:
                meta_text = meta_element.get_text(strip=True)
                if '|' in meta_text:
                    category_parts = meta_text.split('|')
                    publish_time_raw = category_parts[1].strip()
                    
                    publish_time = self.fetch_exact_timestamp(article_url)
                    print(f'time exact: {publish_time}')

                    if not publish_time:
                        publish_time = self.calculate_relative_timestamp(publish_time_raw)
                        print(f'time relative: {publish_time}')
                else:
                    publish_time = ""
            else:
                publish_time = ""
            
            if not publish_time: 
                LOGGER.info(f"Failed to extract publish time for url: {article_url}. Skipping.")
                continue 

            seen.add(article_url)

            if article_title and article_url:
                extracted_article = {
                    'title': article_title,
                    'source': article_url,
                    'timestamp': publish_time
                } 
                self.articles.append(extracted_article)

            if len(self.articles) >= limit:
                break

        LOGGER.info(f'total scraped source of bloomberg technoz: {len(self.articles)}')
        return self.articles

    def fetch_exact_timestamp(self, article_url: str):
        response = requests.get(article_url)
        article_soup = BeautifulSoup(response.content, 'html.parser')
        text_source_container = article_soup.find('div', class_='text-sumber')
        
        if text_source_container:
            time_element = text_source_container.find('h5', class_='title fw4 cl-gray margin-bottom-no')
            if time_element:
                raw_time_string = time_element.get_text(strip=True)

                try:
                    # Parses format: "05 March 2026 09:40"
                    parsed_date = datetime.strptime(raw_time_string, "%d %B %Y %H:%M")
                    return parsed_date.strftime("%Y-%m-%d %H:%M:%S")
                
                except ValueError:
                    return ""
                
        return ""
    
    def calculate_relative_timestamp(self, relative_time_string):
        current_time = datetime.now()
        
        minutes_match = re.search(r'(\d+)\s+menit', relative_time_string)
        if minutes_match:
            minutes = int(minutes_match.group(1))
            calculated_time = current_time - timedelta(minutes=minutes)
            return calculated_time.strftime("%Y-%m-%d %H:%M:%S")
            
        hours_match = re.search(r'(\d+)\s+jam', relative_time_string)
        if hours_match:
            hours = int(hours_match.group(1))
            calculated_time = current_time - timedelta(hours=hours)
            # Sets seconds to 00 due to loss of precision in relative time
            return calculated_time.strftime("%Y-%m-%d %H:00:00")
            
        return ""

    def extract_news_pages(self, num_page: int):
        today = datetime.now()
        today_str = today.strftime("%Y-%m-%d")

        limit = num_page * 10
        self.extract_news(self.get_page(today_str), limit)
        time.sleep(1)

        return self.articles
   
    def get_page(self, date) -> str:
        return f"https://www.bloombergtechnoz.com/indeks/market/{date}"  
    

def main():
  scraper = BloombergTechnoz()

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
    uv run -m src.scraper_engine.sources.idx.scrape_bloomberg_technoz <page_number> <filename_saved> <--csv (optional)>
    '''
    main()
