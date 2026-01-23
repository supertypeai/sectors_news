import argparse
import locale

import dateparser

locale.setlocale(locale.LC_TIME, "en_US.UTF-8")

from scraper_engine.base.scraper import Scraper


class IdnMinerScraper(Scraper):
  def extract_news(self, url):
    soup = self.fetch_news(url)
    for item in soup.find_all('div', class_='col-12'):
      link_tag = item.find('a')

      if link_tag and 'href' in link_tag.attrs:
        source = link_tag['href'].strip()

        if '/news/detail/' in source:
            # title tag
            title_tag = link_tag.find('h5', class_='card-title')
            # timestamp tag
            timestamp_container = link_tag.find('div', class_='mb-2 text-muted small')

            if title_tag and timestamp_container:
              title = title_tag.text.strip()
              all_text_parts = timestamp_container.get_text(separator='|', strip=True).split('|')
                        
              if all_text_parts:
                  timestamp_str = all_text_parts[0] # The date is the first element
                  timestamp = dateparser.parse(timestamp_str).strftime("%Y-%m-%d %H:%M:%S")
                  
                  self.articles.append({'title': title, 'source': source, 'timestamp': timestamp})

            else:
              print(f"[IDNMINERSCRAPER] Could not find title or timestamp in a news item, link: {source}")
        
        else:
          print(f"[IDNMINERSCRAPER] Non-news link found: {source}")

      else:
        print(f"[IDNMINERSCRAPER] No '<a>' tag found in this item")
    
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
  