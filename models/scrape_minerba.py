import argparse
from datetime import datetime
import locale
import sys
import os
import dateparser

locale.setlocale(locale.LC_TIME, "en_US.UTF-8")

# Add the parent directory (project root) to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from base_model import Scraper


class MinerbaScraper(Scraper):
  def extract_news(self, url):
    soup = self.fetch_news(url)
    for item in soup.find_all('article'):
      header = item.find('header')
      if header:
        title = header.find('address').find('a').text.strip()
        source = header.find('address').find('a')['href'].strip()
        timestamp = header.find('time').text.strip()
        timestamp = dateparser.parse(timestamp).strftime("%Y-%m-%d %H:%M:%S")
        self.articles.append({'title': title, 'source': source, 'timestamp': timestamp})
    return self.articles
   
  def extract_news_pages(self, num_pages):
    for i in range(num_pages):
      self.extract_news(self.get_page(i+1))
    return self.articles
   
  def get_page(self, page_num):
    return f'https://www.minerba.esdm.go.id/berita/minerba/{page_num}'

def main():
  scraper = MinerbaScraper()

  parser = argparse.ArgumentParser(description="Script for scraping data from minerba")
  parser.add_argument("page_number", type=int, default=1)
  parser.add_argument("filename", type=str, default="minerbaarticles")
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
  python scrape_minerba.py <page_number> <filename_saved> <--csv (optional)>
  '''
  main()
  