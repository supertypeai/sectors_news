from datetime     import datetime 
from urllib.parse import urljoin

from scraper_engine.base.scraper import Scraper

import argparse
import time


class AntaraNewsScraper(Scraper):
    def extract_news(self, url: str):
        soup = self.fetch_news(url)
        article_cards = soup.select("div.card__post.card__post-list")
        
        for card in article_cards:
            title_tag = card.select_one("h2.post_title a")
            if not title_tag:
                continue

            title = title_tag.get_text(strip=True)
            source = title_tag.get('href')
            
            # Ensure the URL is absolute
            source = urljoin(url, source)

            # Get the timestamp for this article
            timestamp = self.get_article_timestamp(source)
            # Standardize the timestamp
            final_date = self.standardize_date(timestamp)
            if not final_date:
                print(f"[Antara News] Failed parse date for url: {source} Skipping")
                continue 

            self.articles.append({
                'title': title,
                'source': source,
                'timestamp': final_date
            })

        return self.articles

    def standardize_date(self, date: str) -> str: 
        try:
            timestamp_clean = date.split(' GMT')[0]
            timestamp_dt = datetime.strptime(timestamp_clean, "%B %d, %Y %H:%M")
            final_timestamp = timestamp_dt.strftime("%Y-%m-%d %H:%M:%S")
            return final_timestamp
        except ValueError as error:
            print(f"Error parsing date '{date}': {error}")
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
        for i in range(1, num_pages+1):
            self.extract_news(self.get_page(i))
            time.sleep(1)
        return self.articles
   
    def get_page(self, page_num: int) -> str:
        return f"https://en.antaranews.com/business-investment/{page_num}"
    

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
  python -m models.scrape_antaranews <page_number> <filename_saved> <--csv (optional)>
  '''
  main()