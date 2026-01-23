from datetime       import datetime
from urllib.parse   import urljoin

from scraper_engine.base.scraper import Scraper

import argparse
import time 


class IndonesiaBusinessPost(Scraper):
    def extract_news(self, url):
        soup = self.fetch_news(url)
        article_cards = soup.select("div.card-box")

        for card in article_cards:
            title_tag = card.select_one("h3.title a")
            if not title_tag:
                continue

            title = title_tag.get_text(strip=True)
            source = title_tag.get('href')
            source = urljoin(url, source)

            # Get the timestamp
            date = self.get_article_timestamp(source)
            final_date = self.standardize_date(date)
            if not final_date:
                print(f"Failed parse date for url: {source}. Skipping")
                continue
            
            self.articles.append({
                'title': title,
                'source': source,
                'timestamp': final_date
            })
        
        return self.articles

    def standardize_date(self, date: str) -> str:
        try:
            final_date = datetime.strptime(date, "%d/%m/%Y")
            final_date = final_date.strftime("%Y-%m-%d %H:%M:%S") 
            return final_date
        except ValueError as error:
            print(f"Error parse the date: {error}")
            return None 

    def get_article_timestamp(self, article_url: str):
        soup = self.fetch_news(article_url)
        if not soup:
            return None

        date_tag = soup.select_one("ul.tags h3.title")
        if date_tag:
            full_text = date_tag.get_text(strip=True)
            try:
                timestamp = full_text.split(' ')[2]
                return timestamp
            except IndexError:
                return None
        return None

    def extract_news_pages(self, num_pages: int):
        categories = [
            "https://indonesiabusinesspost.com/markets-and-finance",
            "https://indonesiabusinesspost.com/corporate-affairs",
            "https://indonesiabusinesspost.com/business-and-investment"
        ]

        for category in categories:
            for page in range(1, num_pages+1):
                url = f"{category}?page={page}"
                self.extract_news(url)
                time.sleep(0.5)

        return self.articles
   
   
def main():
  scraper = IndonesiaBusinessPost()

  parser = argparse.ArgumentParser(description="Script for scraping data from IndonesiaBusinessPost")
  parser.add_argument("page_number", type=int, default=1)
  parser.add_argument("filename", type=str, default="idnbusinesspost")
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
  python -m models.scrape_idn_business_post <page_number> <filename_saved> <--csv (optional)>
  '''
  main()