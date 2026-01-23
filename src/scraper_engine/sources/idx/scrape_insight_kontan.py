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


class InsightKontanScraper(Scraper):
  def extract_news(self, url):
    soup = self.fetch_news(url)
    for item in soup.find_all('div', class_='card__item--horizon'):
      source = item.find('a')['href'].strip()
      body = item.find('div', class_='card__body')
      if body is not None:
        title = body.find('a').find('h2', class_='card__title').text.strip()
        label = body.find('div', class_='card__label')
        if label is not None:
          timestamp = label.find('span', class_='card__date top')
          if timestamp is not None:
            timestamp = timestamp.text.replace("|", "").strip()
            timestamp = dateparser.parse(timestamp).strftime("%Y-%m-%d %H:%M:%S")
            self.articles.append({'title': title, 'source': source, 'timestamp': timestamp})
          else:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.articles.append({'title': title, 'source': source, 'timestamp': timestamp})
    return self.articles
   
  def extract_news_pages(self, num_pages):
    self.extract_news(self.get_page())
    return self.articles
   
  def get_page(self):
    return f'https://insight.kontan.co.id/'

def main():
  scraper = InsightKontanScraper()

  parser = argparse.ArgumentParser(description="Script for scraping data from kontan")
  parser.add_argument("page_number", type=int, default=1)
  parser.add_argument("filename", type=str, default="kontanarticles")
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
  python scrape_kontan.py <page_number> <filename_saved> <--csv (optional)>
  '''
  main()
  