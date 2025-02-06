import sys
import os
import argparse

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from base_model.scraper_collection import ScraperCollection
from models.scrape_idnfinancials import IDNFinancialScraper
from models.scrape_petromindo import PetromindoScraper
from models.scrape_icn import ICNScraper
from models.scrape_gapki import GapkiScraper
from scripts.server import post_source

def main():
  idnscraper = IDNFinancialScraper()
  petromindoscraper = PetromindoScraper()
  icnscraper = ICNScraper()
  gapkiscraper = GapkiScraper()
  
  scrapercollection = ScraperCollection()
  scrapercollection.add_scraper(idnscraper)
  # scrapercollection.add_scraper(petromindoscraper)
  scrapercollection.add_scraper(icnscraper)
  scrapercollection.add_scraper(gapkiscraper)

  parser = argparse.ArgumentParser(description="Script for scraping data with pipeline")
  parser.add_argument("page_number", type=int, default=1)
  parser.add_argument("filename", type=str, default="scraped_articles")
  parser.add_argument("--csv", action='store_true', help="Flag to indicate write to csv file")

  args = parser.parse_args()

  num_page = args.page_number

  scrapercollection.run_all(num_page)
    
  scrapercollection.write_json(scrapercollection.articles, args.filename)

  if args.csv:
     scrapercollection.write_csv(scrapercollection.articles, args.filename)
  
  post_source(args.filename)

if __name__ == "__main__":
    main()

# python scripts/pipeline.py page_num filename --csv