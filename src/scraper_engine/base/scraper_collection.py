from .scraper import Scraper

from datetime import datetime, timezone, timedelta

import json
import csv
import logging

WIB = timezone(timedelta(hours=7))


LOGGER = logging.getLogger(__name__)


class ScraperCollection:
    scrapers: list[Scraper]
    articles: list
  
    def __init__(self):
        self.scrapers = []
        self.articles = []
    
    def add_scraper(self, scraper) -> None:
        self.scrapers.append(scraper)
    
    def run_all(self, num_page: int | None, date: str | None) -> list[dict]:
        if date is None:
            date = datetime.now(WIB).strftime("%Y%m%d")

        for scraper in self.scrapers:
            try:
                try:
                    articles = scraper.extract_news_pages(num_page, date)
                except TypeError:
                    articles = scraper.extract_news_pages(num_page)

                self.articles = [*self.articles, *articles]

            except Exception as error:
                LOGGER.error(f"Error in scraper {scraper.__class__.__name__}: {error}")
                continue

        return self.articles
    
    # Writer methods
    def write_json(self, jsontext, source: str, filename: str):
        with open(f'./data/{source}/{filename}.json', 'w') as f:
            json.dump(jsontext, f, indent=4)

    def write_file_soup(self, filetext, filename):
        with open(f'./data/{filename}.txt', 'w', encoding='utf-8') as f:
            f.write(filetext.prettify())

    def write_csv(self, data, source: str, filename: str):
        with open(f'./data/{source}/{filename}.csv', 'w', newline='', encoding='utf-8') as csv_file:
            csv_writer = csv.writer(csv_file)
                
            header = data[0].keys()
            csv_writer.writerow(header)

            for item in data:
                csv_writer.writerow(item.values())