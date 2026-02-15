from datetime import datetime, timedelta

from scraper_engine.base.scraper import SeleniumScraper

import argparse
import re
import logging


LOGGER = logging.getLogger(__name__)


class KontanScraper(SeleniumScraper):
    def extract_news(self, url):
        soup = self.fetch_news_with_selenium(url)

        news_list = soup.find("div", class_="list-berita")
        if news_list:
            articles = news_list.find_all("li")
            for article in articles:
                # Find the 'a' tag within the 'h1' for the title and URL
                title_element = article.select_one("h1 > a")

                # Find the span for the date
                date_element = article.select_one("span.font-gray")

                if title_element and date_element:
                    # Extract the data
                    title = title_element.get_text(strip=True)
                    article_url = title_element.get('href')
                    
                    # Get date text and clean it by removing the leading '|' and spaces
                    date = date_element.get_text(strip=True).lstrip('| ')

                    # Standardize date
                    final_date = self.standardize_date(date)

                    if not final_date:
                        print(f"[Kontan] Failed parse date for url: {article_url} Skipping")
                        continue 

                    article_data = {
                        'title': title,
                        'source': article_url,
                        'timestamp': final_date
                    }

                    self.articles.append(article_data)

        LOGGER.info(f'total scraped source of kontan: {len(self.articles)}')
        return self.articles
    
    def standardize_date(self, date: str): 
        current_date = datetime.now()
        try:
            jam_match = re.search(r"(\d+)\s*Jam", date)
            menit_match = re.search(r"(\d+)\s*Menit", date)
            
            hours = int(jam_match.group(1)) if jam_match else 0
            minutes = int(menit_match.group(1)) if menit_match else 0

            result_date = current_date - timedelta(hours=hours, minutes=minutes)
            return result_date.strftime("%Y-%m-%d %H:%M:%S")

        except ValueError as error:
            LOGGER.error(f"Error parse the date kontan: {error}")
            return None 

    def extract_news_pages(self, num_pages: int):
        current_date = datetime.now()

        base_url = (
            f"https://www.kontan.co.id/search/indeks"
            f"?kanal=investasi"
            f"&tanggal={current_date.day}"
            f"&bulan={current_date.month}"
            f"&tahun={current_date.year}"
            f"&pos=indeks"
        )
        # Page num params for kontan 10, 20, 30 
        format_num_pages = num_pages * 10
        for index in range(10, format_num_pages+1, 10):
            # Bypass url for the first page to get all the articles
            if index == 10: 
                self.extract_news(base_url)
            else: 
                url = f"{base_url}&per_page={index}"
                self.extract_news(url)
        
        return self.articles


def main():
  scraper = KontanScraper()

  parser = argparse.ArgumentParser(description="Script for scraping data from kontan.co.id category investasi")
  parser.add_argument("page_number", type=int, default=1)
  parser.add_argument("filename", type=str, default="abafarticles")
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
  uv run -m src.scraper_engine.sources.idx.scrape_kontan <page_number> <filename_saved> <--csv (optional)>
  '''
  main()