import argparse
import sys
import os
import dateparser

# Add the parent directory (project root) to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from base_model import Scraper


class ICNScraper(Scraper):
  def extract_news(self, url):
    soup = self.fetch_news(url)
    for item in soup.find_all('article'):
      div = item.find('div', class_='elementor-post__card')
      if div:
        title = div.find('div', class_='elementor-post__text').find('h3', class_='elementor-post__title').find('a').text.strip()
        source = div.find('a', class_='elementor-post__thumbnail__link')['href'].strip()
        timestamp = div.find('div', class_='elementor-post__meta-data').find('span', class_='elementor-post-date').text.strip()
        timestamp = dateparser.parse(timestamp).strftime("%Y-%m-%d %H:%M:%S")
        self.articles.append({'title': title, 'source': source, 'timestamp': timestamp})
    return self.articles
   
  def extract_news_pages(self, num_pages):
    for i in range(num_pages):
      self.extract_news(self.get_page(i))
    return self.articles
   
  def get_page(self, page_num):
    return f'https://www.indonesiancoalandnickel.com/lintasan-berita/page/{page_num}/'

def main():
  scraper = ICNScraper()

  parser = argparse.ArgumentParser(description="Script for scraping data from indonesiancoalandnickel")
  parser.add_argument("page_number", type=int, default=1)
  parser.add_argument("filename", type=str, default="icnarticles")
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
  python scrape_icn.py <page_number> <filename_saved> < --csv (optional) >
  '''
  main()
  