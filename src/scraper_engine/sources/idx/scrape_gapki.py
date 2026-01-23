import argparse
from datetime import datetime
import sys
import os

# Add the parent directory (project root) to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from base_model.scraper import SeleniumScraper 


class GapkiScraper(SeleniumScraper):
  def extract_news(self, url):
    soup = self.fetch_news_with_selenium(url)

    for item in soup.find_all('article', class_='post'):
      # Some articles have the link in the title (h2), others in the thumbnail
      link_element = item.select_one('h2.blog-entry-title a, .nv-post-thumbnail-wrap a')
      
      # The time tag has different classes for different articles ('updated' or 'entry-date')
      time_element = item.select_one('time.updated, time.entry-date')

      if link_element and time_element:
        title = link_element.get('title', '').strip()
        source = link_element.get('href', '').strip()
        timestamp_str = time_element.get('datetime', '').strip()
        
        # Final check all data
        if not all([title, source, timestamp_str]):
          print(f"Skipping an article because it's missing crucial information.")
          continue

        try:
          # Convert the ISO format timestamp to a more standard format.
          timestamp = datetime.fromisoformat(timestamp_str).strftime("%Y-%m-%d %H:%M:%S")
          
          self.articles.append({'title': title, 'source': source, 'timestamp': timestamp})
        except ValueError as error:
          print(f"Skipping article due to invalid date format: {timestamp_str} - {error}")

      else:
        print(f'[GAPKI.ID] Could not find link element and time element')

    return self.articles
   
  def extract_news_pages(self, num_pages):
    for i in range(num_pages):
      self.extract_news(self.get_page(i))
    return self.articles
   
  def get_page(self, page_num):
    return f'https://gapki.id/en/news/category/recent-news/page/{page_num}/'

def main():
  scraper = GapkiScraper()

  parser = argparse.ArgumentParser(description="Script for scraping data from gapki")
  parser.add_argument("page_number", type=int, default=1)
  parser.add_argument("filename", type=str, default="gapkiarticles")
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
  python scrape_gapki.py <page_number> <filename_saved> < --csv (optional) >
  '''
  main()
  