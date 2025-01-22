import json
import argparse
import sys
import os

# Add the parent directory (project root) to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from base_model import Scraper

class IDXScraper(Scraper):
  def extract_news(self, url):
    data = self.fetch_news_with_proxy(url)
    data = json.loads(data)

    for item in data['Items']:
       title = item['Title']
       timestamp = item['PublishedDate']
       body = item['Summary']
       source = item['Links'][0]['Href']
       tags = item['Tags']
       self.articles.append({'title': title, 'body': body, 'source': source, 'timestamp': timestamp, 'tags': tags})
    return self.articles
  
  def extract_news_pages(self, num_pages, page_size):
    for i in range(num_pages):
      self.extract_news(self.get_page(i, page_size))
    return self.articles

  def get_page(self, page_num, page_size):
    return f"https://www.idx.co.id/primary/NewsAnnouncement/GetNewsSearch?locale=id-id&pageNumber={page_num}&pageSize={page_size}"

def main():
  scraper = IDXScraper()

  parser = argparse.ArgumentParser(description="Script for scraping data from idx")
  parser.add_argument("page_number", type=int, default=1)
  parser.add_argument("page_size", type=int, default=100, help="Page size max is 1000")
  parser.add_argument("filename", type=str, default="idxarticles")
  parser.add_argument("--csv", action='store_true', help="Flag to indicate write to csv file")

  args = parser.parse_args()

  num_page = args.page_number
  size_page = args.page_size
  
  scraper.extract_news_pages(num_page, size_page)
    
  scraper.write_json(scraper.articles, args.filename)

  if args.csv:
     scraper.write_csv(scraper.articles, args.filename)

if __name__ == "__main__":
    main()