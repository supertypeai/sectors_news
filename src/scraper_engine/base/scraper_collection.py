from copy import deepcopy
from datetime import datetime, timezone, timedelta
from pathlib import Path

from .scraper import Scraper
from scraper_engine.utils.json_helpers import (
    write_csv as write_csv_file,
    write_json as write_json_file,
)

import logging
import inspect 
import time


WIB = timezone(timedelta(hours=7))

LOGGER = logging.getLogger(__name__)


class ScraperCollection:
    scrapers: list[Scraper]
    articles: list
    scraper_results: list[dict]
  
    def __init__(self):
        self.scrapers = []
        self.articles = []
        self.scraper_results = []
    
    def add_scraper(self, scraper) -> None:
        self.scrapers.append(scraper)
    
    def run_all(
        self, 
        num_page: int | None, 
        date: str | None, 
        filter_from: datetime | None,
    ) -> list[dict]:
        today = datetime.now(WIB)
        self.scraper_results = []
        
        if date is None:
            date = today.strftime("%Y%m%d")

        dates_to_scrape = [date]

        if filter_from and filter_from.date() < today.date():
            yesterday = (today - timedelta(days=1)).strftime("%Y%m%d")
            if yesterday not in dates_to_scrape:
                dates_to_scrape.append(yesterday)

        for date_to_scrape in dates_to_scrape:
            for scraper in self.scrapers:
                scraper.articles = [] 
                scraper.reset_health()
                scraper_articles = []

                start_time = time.perf_counter()
                
                try:
                    extract_params = inspect.signature(
                        scraper.extract_news_pages
                    ).parameters
                    
                    if "date" in extract_params or "target_date" in extract_params:
                        scraper_articles = scraper.extract_news_pages(
                            num_page,
                            date_to_scrape,
                        )
                    
                    else:
                        scraper_articles = scraper.extract_news_pages(num_page)

                    self.articles.extend(scraper_articles)
                
                except Exception as error:
                    LOGGER.error(
                        "Error in scraper %s: %s",
                        scraper.__class__.__name__,
                        error,
                    )

                duration_minutes = (
                    time.perf_counter() - start_time
                ) / 60

                scraper_result = {
                    "source": scraper.__class__.__name__,
                    "date": date_to_scrape,
                    "articles_found": (
                        len(scraper_articles)
                        if scraper_articles is not None
                        else 0
                    ),
                    "duration_minutes": duration_minutes,
                    **deepcopy(scraper.health),
                }

                self.scraper_results.append(scraper_result)

        return self.articles

    def close_scrapling_sessions(self) -> None:
        for scraper in self.scrapers:
            scraper.close_scrapling_session()
            
    # Writer methods
    def write_json(self, jsontext, source: str, filename: str):
        json_path = Path("data") / source / f"{filename}.json"
        write_json_file(json_path, jsontext, indent=4)

    def write_csv(self, data, source: str, filename: str):
        csv_path = Path("data") / source / f"{filename}.csv"
        write_csv_file(csv_path, data)
