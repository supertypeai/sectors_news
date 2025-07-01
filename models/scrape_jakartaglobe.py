import argparse
from datetime import datetime, timedelta
import locale
import re
import sys
import os

locale.setlocale(locale.LC_TIME, "en_US.UTF-8")

# Add the parent directory (project root) to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from base_model import Scraper


class JGScraper(Scraper):
  def extract_news(self, url):
    soup = self.fetch_news_with_proxy(url)
    
    for item in soup.find_all('div', class_='row mb-4 position-relative'):
      source = 'https://jakartaglobe.id' + item.find('div', class_='col-4').find('a')['href'].strip()
      title = item.find('div', class_='col-8 pt-l').find('h4').text.strip()
      body = item.find('div', class_='col-8 pt-l').find('span', class_='text-muted text-truncate-2-lines').text.strip()
      timestamp = item.find('div', class_='col-8 pt-l').find('span', class_='text-muted small').text.strip()
      timestamp = self.convert_to_timestamp(timestamp)
      self.articles.append({'title': title, 'body': body, 'source': source, 'timestamp': timestamp})
    return self.articles
  
  def convert_to_timestamp(self, time_str):
    # Check if the string is in the absolute date format
    try:
        absolute_time = datetime.strptime(time_str, "%b %d, %Y | %I:%M %p")
        return absolute_time.strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        pass
    
    # Check if the string is in the relative time format
    match = re.match(r"(\d+)\s+(hour[s]?|day[s]?)\s+ago", time_str)
    if match:
        value = int(match.group(1))
        unit = match.group(2)
        if 'hour' in unit:
            relative_time = datetime.now() - timedelta(hours=value)
        elif 'day' in unit:
            relative_time = datetime.now() - timedelta(days=value)
        return relative_time.strftime("%Y-%m-%d %H:%M:%S")
    
    return None
   
  def extract_news_pages(self, num_pages):
    for i in range(num_pages):
      self.extract_news(self.get_page(i+1))
    return self.articles
   
  def get_page(self, page_num):
    return f'https://jakartaglobe.id/business/newsindex/{page_num}'

def main():
  scraper = JGScraper()

  parser = argparse.ArgumentParser(description="Script for scraping data from jakartaglobe")
  parser.add_argument("page_number", type=int, default=1)
  parser.add_argument("filename", type=str, default="jgarticles")
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
  python scrape_jakartaglobe.py <page_number> <filename_saved> <--csv (optional)>
  '''
  main()
  