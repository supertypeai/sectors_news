import argparse
import locale
import sys
import os
import dateparser

locale.setlocale(locale.LC_TIME, "en_US.UTF-8")

# Add the parent directory (project root) to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from base_model import Scraper


class IdnMinerScraper(Scraper):
  def extract_news(self, url):
    soup = self.fetch_news(url)
    for item in soup.find_all('div', class_='col-12'):
      source = item.find('a')['href'].strip()
      box = item.find('div', class_='box-news')
      if box:
        title = box.find('div', class_='content').find('h4').text.strip()
        timestamp = box.find('div', class_='image').find('div', class_='date').text.strip()
        timestamp = dateparser.parse(timestamp).strftime("%Y-%m-%d %H:%M:%S")
        self.articles.append({'title': title, 'source': source, 'timestamp': timestamp})
    return self.articles
   
  def extract_news_pages(self, num_pages):
    for i in range(num_pages):
      self.extract_news(self.get_page(i+1))
    return self.articles
   
  def get_page(self, page_num):
    return f'https://indonesiaminer.com/news?page={page_num}'

def main():
  scraper = IdnMinerScraper()

  parser = argparse.ArgumentParser(description="Script for scraping data from indonesian miner")
  parser.add_argument("page_number", type=int, default=1)
  parser.add_argument("filename", type=str, default="idnminerarticles")
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
  python scrape_idnminer.py <page_number> <filename_saved> <--csv (optional)>
  '''
  main()
  