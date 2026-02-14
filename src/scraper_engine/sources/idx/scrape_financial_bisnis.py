from datetime import datetime, timedelta

from scraper_engine.base.scraper import SeleniumScraper

import argparse
import time
import re 
import logging 


LOGGER = logging.getLogger(__name__)


class FinansialBisnisScraper(SeleniumScraper):
    def extract_news(self, url):
        soup = self.fetch_news_with_selenium(url)
        
        article_container = soup.find("div", id="indeksListView")

        if article_container:
            # Find all individual article items
            articles = article_container.find_all("div", class_="artItem")

            for article in articles:
                # Find the 'a' tag that contains the link
                link_element = article.find("a", class_="artLink")
                
                # Find the 'h4' tag for the title
                title_element = article.find("h4", class_="artTitle")
                
                # Find the 'div' for the date
                date_element = article.find("div", class_="artDate")

                if link_element and title_element and date_element:
                    article_url = link_element.get('href')
                    title = title_element.get_text(strip=True)

                    # Get date and standardize
                    date = date_element.get_text(strip=True)
                    final_date = self.standardize_date(date)

                    if not final_date:
                        LOGGER.info(f"Failed parse date for url: {article_url}. Skipping")
                        continue

                    article_data = {
                        'title': title,
                        'source': article_url,
                        'timestamp': final_date
                    }
                    self.articles.append(article_data)
        
        LOGGER.info(f'total scraped source of finansial.bisnis: {len(self.articles)}')
        return self.articles
    
    def standardize_date(self, date: str) -> str | None:
        try:
            current_date = datetime.now()

            if "menit yang lalu" in date:
                minutes = int(re.search(r'(\d+)\s*menit', date).group(1))
                result_date = current_date - timedelta(minutes=minutes)
                return result_date.strftime("%Y-%m-%d %H:%M:%S")

            elif "jam yang lalu" in date:
                hours = int(re.search(r'(\d+)\s*jam', date).group(1))
                result_date = current_date - timedelta(hours=hours)
                return result_date.strftime("%Y-%m-%d %H:%M:%S") 
            
            else:
                # Handle absolute date format: "13 Agt 2025 | 09:00 WIB"
                return self.parse_absolute_date(date)
            
        except (ValueError, AttributeError) as error:
            LOGGER.error(f"Error parsing date finansial bisnis {date}: {error}")
            return None 
        
    def parse_absolute_date(self, date: str) -> str | None:
        month_map = {
                'Jan': 'Jan', 'Feb': 'Feb', 'Mar': 'Mar', 'Apr': 'Apr',
                'Mei': 'May', 'Jun': 'Jun', 'Jul': 'Jul', 'Agt': 'Aug',
                'Sep': 'Sep', 'Okt': 'Oct', 'Nov': 'Nov', 'Des': 'Dec'
            }
        date_clean = date.replace("WIB", "")
        date_parts = date_clean.split("|")

        if len(date_parts) == 2:
            date_part = date_parts[0].strip()  
            time_part = date_parts[1].strip()  

            # Parse date part
            day, month_abbr, year = date_part.split()

            if month_abbr in month_map:
                month_eng = month_map.get(month_abbr)

                eng_date_format = f"{day} {month_eng} {year} {time_part}"

                # Parse the date to datetime 
                dt = datetime.strptime(eng_date_format, "%d %b %Y %H:%M")
                
                return dt.strftime("%Y-%m-%d %H:%M:%S")

        return None

    def extract_news_pages(self, num_pages):
        for index in range(1, num_pages+1):
            self.extract_news(self.get_page(index))
            time.sleep(1)
        return self.articles
   
    def get_page(self, page_num) -> str:
        return f"https://www.bisnis.com/index?categoryId=194&page={page_num}"  # id 194 category market
    

def main():
  scraper = FinansialBisnisScraper()

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
  python -m models.scrape_financial_bisnis <page_number> <filename_saved> <--csv (optional)>
  '''
  main()