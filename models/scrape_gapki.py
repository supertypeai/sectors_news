import argparse
from datetime import datetime
import sys
import os

# Add the parent directory (project root) to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from base_model import Scraper


class GapkiScraper(Scraper):
  def extract_news(self, url):
    soup = self.fetch_news_with_proxy(url)
    for item in soup.find_all('article', class_='post'):
      div = item.find('div', class_='article-content-col').find('div', class_='content').find('div', class_='default-post')
      if div:
        title = div.find('div', class_='nv-post-thumbnail-wrap').find('a')['title'].strip()
        source = div.find('div', class_='nv-post-thumbnail-wrap').find('a')['href'].strip()
        timestamp = div.find('div', class_='non-grid-content').find('ul', class_='nv-meta-list').find('li').find('time', class_='updated')['datetime'].strip()
        timestamp = datetime.fromisoformat(timestamp).strftime("%Y-%m-%d %H:%M:%S")
        self.articles.append({'title': title, 'source': source, 'timestamp': timestamp})
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
  