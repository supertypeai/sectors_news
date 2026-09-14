from .scraper import Scraper
from scraper_engine.utils.json_helpers import (
    write_csv as write_csv_file,
    write_json as write_json_file,
)

from datetime import datetime, timezone, timedelta

import logging
import inspect 
from pathlib import Path


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
    
    def run_all(
        self, 
        num_page: int | None, 
        date: str | None, 
        filter_from: datetime | None
    ) -> list[dict]:
        today = datetime.now(WIB)
        
        if date is None:
            date = today.strftime("%Y%m%d")

        dates_to_scrape = [date]

        if filter_from and filter_from.date() < today.date():
            yesterday = (today - timedelta(days=1)).strftime("%Y%m%d")
            dates_to_scrape.append(yesterday)

        for date_to_scrape in dates_to_scrape:
            for scraper in self.scrapers:
                scraper.articles = [] 
                
                try:
                    extract_params = inspect.signature(
                        scraper.extract_news_pages
                    ).parameters
                    
                    if "date" in extract_params or "target_date" in extract_params:
                        articles = scraper.extract_news_pages(
                            num_page, 
                            date_to_scrape
                        )
                    
                    else:
                        articles = scraper.extract_news_pages(num_page)

                    self.articles = [*self.articles, *articles]
                
                except Exception as error:
                    LOGGER.error(
                        "Error in scraper %s: %s",
                        scraper.__class__.__name__,
                        error,
                    )
                    continue

        return self.articles
    
    # Writer methods
    def write_json(self, jsontext, source: str, filename: str):
        json_path = Path("data") / source / f"{filename}.json"
        write_json_file(json_path, jsontext, indent=4)

    def write_csv(self, data, source: str, filename: str):
        csv_path = Path("data") / source / f"{filename}.csv"
        write_csv_file(csv_path, data)
