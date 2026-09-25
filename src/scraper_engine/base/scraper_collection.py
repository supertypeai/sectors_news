from copy import deepcopy
from datetime import datetime, timezone, timedelta
from pathlib import Path

from .scraper import Scraper, SeleniumScraper
from scraper_engine.utils.json_helpers import (
    write_csv as write_csv_file,
    write_json as write_json_file,
)

import logging
import inspect 
import time
import asyncio


LOGGER = logging.getLogger(__name__)


class ScraperCollection:
    scrapers: list[Scraper]
    articles: list
    scraper_results: list[dict]

    def __init__(self):
        self.scrapers = []
        self.articles = []
        self.scraper_results = []

    def add_scraper(self, scraper: Scraper) -> None:
        self.scrapers.append(scraper)

    def _run_scraper(
        self,
        scraper: Scraper,
        num_page: int | None,
        date_to_scrape: str,
    ) -> tuple[list, dict]:
        scraper.articles = []
        scraper.reset_health()

        scraper_articles = []
        start_time = time.perf_counter()

        LOGGER.info(
            "Processing scraper %s for %s",
            scraper.__class__.__name__,
            date_to_scrape,
        )
        
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

        except Exception as error:
            LOGGER.error(
                "Error in scraper %s: %s",
                scraper.__class__.__name__,
                error,
            )

        scraper_articles = scraper_articles or []

        duration_minutes = (
            time.perf_counter() - start_time
        ) / 60

        scraper_result = {
            "source": scraper.__class__.__name__,
            "date": date_to_scrape,
            "articles_found": len(scraper_articles),
            "duration_minutes": duration_minutes,
            **deepcopy(scraper.health),
        }

        return scraper_articles, scraper_result

    async def _run_scraper_concurrently(
        self,
        scraper: Scraper,
        num_page: int | None,
        date_to_scrape: str,
        semaphore: asyncio.Semaphore,
    ) -> tuple[list, dict]:
        async with semaphore:
            return await asyncio.to_thread(
                self._run_scraper,
                scraper,
                num_page,
                date_to_scrape,
            )

    async def _run_selenium_scrapers(
        self,
        scrapers: list[Scraper],
        num_page: int | None,
        date_to_scrape: str,
    ) -> list[tuple[list, dict]]:
        results = []

        for scraper in scrapers:
            result = await asyncio.to_thread(
                self._run_scraper,
                scraper,
                num_page,
                date_to_scrape,
            )

            results.append(result)

        return results

    async def run_all(
        self,
        num_page: int | None,
        date: str | None,
        filter_from: datetime | None,
        max_concurrency: int = 5,
    ) -> list:
        today = datetime.now(filter_from.tzinfo)

        self.articles = []
        self.scraper_results = []

        if date is None:
            date = today.strftime("%Y%m%d")

        dates_to_scrape = [date]

        if filter_from and filter_from.date() < today.date():
            yesterday = (
                today - timedelta(days=1)
            ).strftime("%Y%m%d")

            if yesterday not in dates_to_scrape:
                dates_to_scrape.append(yesterday)

        semaphore = asyncio.Semaphore(max_concurrency)

        concurrent_scrapers = [
            scraper
            for scraper in self.scrapers
            if not isinstance(scraper, SeleniumScraper)
        ]

        selenium_scrapers = [
            scraper
            for scraper in self.scrapers
            if isinstance(scraper, SeleniumScraper)
        ]

        for date_to_scrape in dates_to_scrape:
            tasks = [
                self._run_scraper_concurrently(
                    scraper,
                    num_page,
                    date_to_scrape,
                    semaphore,
                )
                for scraper in concurrent_scrapers
            ]

            if selenium_scrapers:
                selenium_task = self._run_selenium_scrapers(
                    selenium_scrapers,
                    num_page,
                    date_to_scrape,
                )

                concurrent_results, selenium_results = await asyncio.gather(
                    asyncio.gather(*tasks),
                    selenium_task,
                )

                results = [
                    *concurrent_results,
                    *selenium_results,
                ]

            else:
                results = await asyncio.gather(*tasks)

            for scraper_articles, scraper_result in results:
                self.articles.extend(scraper_articles)
                self.scraper_results.append(scraper_result)

        return self.articles

    def close_scrapling_sessions(self) -> None:
        for scraper in self.scrapers:
            scraper.close_scrapling_session()

    def write_json(
        self,
        jsontext,
        source: str,
        filename: str,
    ) -> None:
        json_path = Path("data") / source / f"{filename}.json"
        write_json_file(
            json_path,
            jsontext,
            indent=4,
        )

    def write_csv(
        self,
        data,
        source: str,
        filename: str,
    ) -> None:
        csv_path = Path("data") / source / f"{filename}.csv"
        write_csv_file(
            csv_path,
            data,
        )