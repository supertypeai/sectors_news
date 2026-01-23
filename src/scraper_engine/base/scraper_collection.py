from .scraper import Scraper

import json
import csv


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