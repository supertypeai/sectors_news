from datetime       import datetime 
from urllib.parse   import urljoin

from base_model.scraper import Scraper

import argparse
import time


class AsianTelekom(Scraper):
    def extract_news(self, url: str):
        soup = self.fetch_news(url)
    
        if not soup:
            return

        # Find all article containers on the list page
        article_items = soup.select("div.item.with-border-bottom")
       
        for item in article_items:
            title_tag = item.select_one("h2.item__title a")
        
            if not title_tag:
                continue

            title = title_tag.get_text(strip=True)
           
            article_link = title_tag.get('href')
            
            # Ensure the link is absolute
            article_link = urljoin(url, article_link)
            
            # Visit the article link to get the date 
            date = self.get_article_date(article_link)
            final_date = self.standardize_date(date)
            if not final_date:
                print(f"Failed parse date for url: {article_link}. Skipping")
                continue 

            article_data = {
                'title': title,
                'source': article_link,
                'date': final_date,
            }
            self.articles.append(article_data)

        return self.articles

    def standardize_date(self, date: str) -> str | None:
        try:
            date_dt = datetime.fromisoformat(date.replace('Z', '+00:00'))
            final_date = date_dt.strftime("%Y-%m-%d %H:%M:%S")
            return final_date
        except ValueError as error:
            print(f"Error parsing date '{date}': {error}")
            return None 

    def get_article_date(self, article_url: str) -> str | None:
        soup = self.fetch_news(article_url)
        if not soup:
            return None
        
        # Find the <time> tag 
        time_tag = soup.select_one("time[pubdate]")
        
        if time_tag and time_tag.has_attr('datetime'):
            return time_tag['datetime']
        else:
            return None

    def extract_news_pages(self, num_pages):
        for i in range(num_pages):
            page_url = self.get_page(i)
            self.extract_news(page_url)
            time.sleep(1)
        return self.articles
    
    def get_page(self, page_num) -> str:
        return f"https://asiantelecom.com/market/indonesia?page={page_num}"


def main():
  scraper = AsianTelekom()

  parser = argparse.ArgumentParser(description="Script for scraping data from asiantelekom")
  parser.add_argument("page_number", type=int, default=1)
  parser.add_argument("filename", type=str, default="asiantelekom")
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
  python -m models.scrape_asian_telekom <page_number> <filename_saved> <--csv (optional)>
  '''
  main()