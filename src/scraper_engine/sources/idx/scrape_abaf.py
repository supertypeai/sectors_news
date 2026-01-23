import argparse
from datetime import datetime, timedelta
import locale
import re
import sys
import os
import dateparser

locale.setlocale(locale.LC_TIME, "en_US.UTF-8")

from scraper_engine.base import Scraper


class AbafScraper(Scraper):
  def extract_news(self, url):
    soup = self.fetch_news(url)
    
    headline = soup.find('div', class_='item--large with-border-bottom')
    if headline:
      item = headline.find('div').find('h2').find('a')
      title = item.text.strip()
      source = item['href'].strip()
      timestamp = headline.find('div').find('div', class_='content-right').find('div', class_='item-details').find('div', class_='if-date')
      if timestamp:
        timestamp = timestamp.text.strip()
        timestamp = self.convert_to_timestamp(timestamp)
        self.articles.append({'title': title, 'source': source, 'timestamp': timestamp})
      else:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.articles.append({'title': title, 'source': source, 'timestamp': timestamp})
    for item in soup.find_all('div', class_='item with-border-bottom'):
      h2 = item.find('h2')
      if h2 is not None:
        header = h2.find('a')
        title = header.text.strip()
        source = header['href'].strip()
        timestamp = item.find('div').find('div', class_='content-right').find('div', class_='item-details').find('div', class_='if-date')
        if timestamp:
          timestamp = timestamp.text.strip()
          timestamp = self.convert_to_timestamp(timestamp)
          self.articles.append({'title': title, 'source': source, 'timestamp': timestamp})
        else:
          timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
          self.articles.append({'title': title, 'source': source, 'timestamp': timestamp})
    return self.articles
    
  def convert_to_timestamp(self, time_str):
    match = re.match(r"(\d+)\s+(hour[s]?|day[s]?)\s+ago", time_str)
    if match:
      value = int(match.group(1))
      unit = match.group(2)
      if 'hour' in unit:
        timestamp = datetime.now() - timedelta(hours=value)
      elif 'day' in unit:
        timestamp = datetime.now() - timedelta(days=value)
      return timestamp.strftime("%Y-%m-%d %H:%M:%S")
    return None
   
  def extract_news_pages(self, num_pages):
    for i in range(num_pages):
      self.extract_news(self.get_page(i))
    return self.articles
   
  def get_page(self, page_num):
    return f'https://asianbankingandfinance.net/market/indonesia?page={page_num}'

def main():
  scraper = AbafScraper()

  parser = argparse.ArgumentParser(description="Script for scraping data from asianbankingandfinance")
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
  python scrape_abaf.py <page_number> <filename_saved> <--csv (optional)>
  '''
  main()
  