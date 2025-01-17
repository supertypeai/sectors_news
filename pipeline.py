from models.scrape_idnfinancials import IDNFinancialScraper
import argparse
from scripts.server import post_source

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
  
  post_source(args.filename)

if __name__ == "__main__":
    main()

# python pipeline.py page_num filename --csv