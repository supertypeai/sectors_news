from datetime import datetime
from urllib.parse import urljoin

from scraper_engine.base.scraper import SeleniumScraper

import argparse
import time 
import re
import logging 


LOGGER = logging.getLogger(__name__)


class JakartaPost(SeleniumScraper):
    def extract_news(self, url):
        soup = self.fetch_news_with_selenium(url)
        
        if 'business/markets' in url:
            article_containers = soup.select("div.listNews")
            for article in article_containers:
                premium_badge = article.select_one("span.premiumBadge")

                if premium_badge:
                    continue 

                link_tag = article.select_one("a[href*='/business/']")
                title_tag = article.select_one("h2.titleNews")

                if link_tag and title_tag:
                    title = title_tag.get_text(strip=True)
                    
                    # Joined with base url
                    relative_url = link_tag.get('href')
                    relative_url = re.sub(r"\.html-\d+$", ".html", relative_url)
                    source = urljoin("https://www.thejakartapost.com", relative_url)
                    
                    # Get date from url and standardize
                    date_match = re.search(r'/(\d{4}/\d{2}/\d{2})/', relative_url)

                    if date_match:
                        final_date = date_match.group(1).replace('/', '-')
                    else:
                        LOGGER.info(f"[business/market] Could not find date in URL: {relative_url}. Skipping.")
                        continue
                    
                    final_date = self.standardized_date(final_date)

                    if not final_date:
                        LOGGER.info(f"[business/market] Failed parse date for url: {source}. Skipping")
                        continue 

                    article_data = {
                        'title': title,
                        'source': source,
                        'timestamp': final_date,
                    }

                    self.articles.append(article_data)

            LOGGER.info(f'total scraped source of jakarta post: {len(self.articles)}')
            return self.articles 
        
        else:
            results = soup.find_all('div', class_='gsc-webResult gsc-result')

            for result in results:
                # Get title tag
                title_tag = result.find('a', class_='gs-title')
                # Find the snippet to get the date
                snippet_tag = result.find('div', class_='gs-bidi-start-align gs-snippet')

                if title_tag and snippet_tag:
                    title = title_tag.get_text(strip=True)
                    source = title_tag['href'] 
                    
                    snippet_text = snippet_tag.get_text(strip=True)
                    date = snippet_text.split('...')[0].strip()
                    final_date = self.standardized_date(date)

                    if not final_date:
                        LOGGER.info(f"[ivesment search] Failed parse date for url: {source}. Skipping")
                        continue 

                    article_data = {
                        'title': title,
                        'source': source,
                        'timestamp': final_date
                    }
                    self.articles.append(article_data)
            
            LOGGER.info(f'total scraped source of jakarta post: {len(self.articles)}')
            return self.articles
    
    def standardized_date(self, date: str):
        try:
            if '-' in date:
                date_dt = datetime.strptime(date, "%Y-%m-%d")
                final_date = date_dt.strftime("%Y-%m-%d %H:%M:%S")
            else:
                # Parse Format "16 Aug 2016" (day month year)
                try:
                    date_dt = datetime.strptime(date, '%d %b %Y')
                    final_date = date_dt.strftime("%Y-%m-%d %H:%M:%S")
                except ValueError:
                    # Parse Format "16 Aug 2016" (day month year)
                    try:
                        date_dt = datetime.strptime(date, '%d %b %Y')
                        final_date = date_dt.strftime("%Y-%m-%d %H:%M:%S")
                    except ValueError:
                        # Parse Format "Jan 13, 2020" (month day, year)
                        try:
                            date_dt = datetime.strptime(date, '%b %d, %Y')
                            final_date = date_dt.strftime("%Y-%m-%d %H:%M:%S")
                        except ValueError as error:
                            LOGGER.error(f"Error parse the date: {error}")
                            return None
            
            return final_date

        except ValueError as error:
            LOGGER.error(f"Error parse the date: {error}")
            return None 

    def extract_news_pages(self, num_pages: int):
        article_list = ['https://www.thejakartapost.com/business/markets']
                        # 'https://www.thejakartapost.com/search?q=investment#gsc.tab=0&gsc.q=investment&gsc.sort=date'] 
        
        for url_article in article_list:
            for page in range(1, num_pages+1):
                if 'business/markets' in url_article:
                    url = f"{url_article}?page={page}"
                else:
                    url = f"{url_article}&gsc.page={page}"
                self.extract_news(url)
                time.sleep(1)

        return self.articles
    

def main():
  scraper = JakartaPost()

  parser = argparse.ArgumentParser(description="Script for scraping data from thejakartapost")
  parser.add_argument("page_number", type=int, default=1)
  parser.add_argument("filename", type=str, default="thejakartapost")
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
  python -m models.scrape_jakartapost <page_number> <filename_saved> <--csv (optional)>
  '''
  main()