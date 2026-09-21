from types import MethodType

from bs4 import BeautifulSoup
from scrapling.fetchers import StealthySession

from scraper_engine.sources.idx.scrape_investor_id import InvestorID
from scraper_engine.sources.idx.scrape_kontan_investasi import KontanInvestasi

import logging


LOGGER = logging.getLogger(__name__)


def create_stealthy_fetcher(session: StealthySession):
    def fetch_with_browser(self, url: str):
        LOGGER.info(
            "[STEALTH TEST] Fetching %s",
            url,
        )

        response = session.fetch(
            url,
            google_search=False,
            network_idle=True,
        )

        LOGGER.info(
            "[STEALTH TEST] status=%d url=%s",
            response.status,
            url,
        )

        if response.status != 200:
            LOGGER.warning(
                "[STEALTH TEST] Non-200 status=%d url=%s",
                response.status,
                url,
            )
            return None

        return BeautifulSoup(
            bytes(response.body),
            "html.parser",
        )

    return fetch_with_browser


def run_scraper(
    scraper,
    source_name: str,
    target_date: str,
    landing_url: str,
):
    LOGGER.info(
        "=== Testing %s ===",
        source_name,
    )

    with StealthySession(
        headless=True,
        real_chrome=True,
        block_webrtc=True,
    ) as session:
        LOGGER.info(
            "[STEALTH TEST] Opening landing page: %s",
            landing_url,
        )

        landing_response = session.fetch(
            landing_url,
            google_search=False,
            network_idle=True,
        )

        LOGGER.info(
            "[STEALTH TEST] landing status=%d",
            landing_response.status,
        )

        scraper.fetch_news_with_scrapling = MethodType(
            create_stealthy_fetcher(session),
            scraper,
        )

        return scraper.extract_news_pages(
            num_pages=1,
            date=target_date,
            is_use_proxy=False,
        )


def test_scrapers():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )

    target_date = "20260921"

    investor_articles = run_scraper(
        scraper=InvestorID(),
        source_name="Investor ID",
        target_date=target_date,
        landing_url="https://investor.id/",
    )

    kontan_articles = run_scraper(
        scraper=KontanInvestasi(),
        source_name="Kontan Investasi",
        target_date=target_date,
        landing_url="https://www.kontan.co.id/",
    )

    LOGGER.info(
        "Investor ID articles: %d",
        len(investor_articles),
    )

    LOGGER.info(
        "Kontan Investasi articles: %d",
        len(kontan_articles),
    )


if __name__ == "__main__":
    test_scrapers()