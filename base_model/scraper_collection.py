import json
import csv
import sys
import os
from dotenv import load_dotenv

from models.scrape_petromindo import PetromindoScraper

# Determine the base directory where the .env file is located
base_dir = os.path.dirname(os.path.abspath(__file__))  # This will resolve to the directory containing scraper.py
project_root = os.path.abspath(os.path.join(base_dir, '..'))  # Move one level up to the base folder

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from .scraper import Scraper

# Load the .env file from the base directory
load_dotenv(os.path.join(project_root, '.env'))

class ScraperCollection:
  scrapers: list[Scraper]
  articles: list
  
  def __init__(self):
    self.scrapers = []
    self.articles = []
    
  def add_scraper(self, scraper):
    self.scrapers.append(scraper)
  
  def run_all(self, num_page):
    for scraper in self.scrapers:
      try:
        articles = scraper.extract_news_pages(num_page)
        self.articles = [*self.articles, *articles]
      except Exception as e:
        print(f"Error in scraper {scraper.__class__.__name__}: {e}")
        continue
    return self.articles
  
  # Writer methods
  def write_json(self, jsontext, filename):
    with open(f'./data/{filename}.json', 'w') as f:
      json.dump(jsontext, f, indent=4)

  def write_file_soup(self, filetext, filename):
    with open(f'./data/{filename}.txt', 'w', encoding='utf-8') as f:
      f.write(filetext.prettify())

  def write_csv(self, data, filename):
    
    with open(f'./data/{filename}.csv', 'w', newline='', encoding='utf-8') as csv_file:
    
      csv_writer = csv.writer(csv_file)
        
      header = data[0].keys()
      csv_writer.writerow(header)

      for item in data:
        csv_writer.writerow(item.values())