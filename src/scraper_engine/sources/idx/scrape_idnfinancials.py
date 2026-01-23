import argparse

from scraper_engine.base.scraper import Scraper


class IDNFinancialScraper(Scraper):
  def extract_news(self, url):
    soup = self.fetch_news(url)
    for item in soup.find_all('article'):
        div = item.find('div', class_='col-8')
        if div:  
          title = div.find('h2', class_='title').find('a').text
          body = div.find('p', class_='summary').text
          source = div.find('h2', class_='title').find('a')['href']
          timestamp = div.find('p', class_='date-published')['data-date']
          self.articles.append({'title': title, 'body': body, 'source': source, 'timestamp': timestamp})
    return self.articles
   
  def extract_news_pages(self, num_pages):
    for i in range(num_pages):
      self.extract_news(self.get_page(i))
    return self.articles
   
  def get_page(self, page_num):
    return f'https://www.idnfinancials.com/news/page/{page_num}'

def main():
  scraper = IDNFinancialScraper()

  parser = argparse.ArgumentParser(description="Script for scraping data from idnfinancials")
  parser.add_argument("page_number", type=int, default=1)
  parser.add_argument("filename", type=str, default="idnarticles")
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
  python scrape_idnfinancials.py <page_number> <filename_saved> <--csv (optional)>
  '''
  main()