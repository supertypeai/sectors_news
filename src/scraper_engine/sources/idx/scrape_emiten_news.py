from datetime import datetime

from scraper_engine.base.scraper import Scraper

import argparse
import time
import logging 


LOGGER = logging.getLogger(__name__)


class EmitenNews(Scraper):
    def extract_news(self, url):
        soup = self.fetch_news(url)

        wrapper = soup.select_one("div.search-result-wrapper")
        article_cards = wrapper.select("a.news-card-2.search-result-item")
       
        if not article_cards:
            LOGGER.info("Found no article cards. Page structure may have changed or JS failed to load.")
            return []

        for card in article_cards:
            title_tag = card.select_one("p.fs-16")
            source_url = card.get('href') 

            if not title_tag or not source_url:
                continue

            title = title_tag.get_text(strip=True)

            date = self.get_timestamp(source_url)
            final_date = self.standardize_date(date)

            article_data = {
                'title': title,
                'source': source_url,
                'timestamp': final_date
            }

            self.articles.append(article_data)
        
        LOGGER.info(f'total scraped source of asian emiten news: {len(self.articles)}')
        return self.articles
    
    def get_timestamp(self, article_url: str):
        soup = self.fetch_news(article_url)
        timestamp_tag = soup.select_one("span.time-posted")

        try:
            raw_time_str = timestamp_tag.get_text(strip=True)
            date_part = raw_time_str.split(',')[0]
            return date_part
        
        except Exception as error:
            LOGGER.error(f"Error to get date part emitem news: {error}")
            return None 
    
    def standardize_date(self, date: str) -> str | None:
        try:
            date_obj = datetime.strptime(date, "%d/%m/%Y")
            final_date = date_obj.strftime("%Y-%m-%d %H:%M:%S")
            return final_date
        
        except (ValueError, AttributeError) as error:
            LOGGER.error(f"Error parsing date '{date}': {error}")
            return None 

    def extract_news_pages(self, num_pages: int):
        
        for index in range(num_pages):
            page_url = self.get_page(index)
            self.extract_news(page_url)
            time.sleep(1)
        return self.articles
   
    def get_page(self, page_num) -> str:
        page_num *= 9
        return f"https://emitennews.com/category/emiten/{page_num}"
    

def main():
  scraper = EmitenNews()

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
  python -m models.scrape_emiten_news <page_number> <filename_saved> <--csv (optional)>
  '''
  main()