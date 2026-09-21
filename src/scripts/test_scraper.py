from types import MethodType

from scraper_engine.base.scraper import Scraper
from scraper_engine.sources.idx.scrape_investor_id import InvestorID
from scraper_engine.sources.idx.scrape_kontan_investasi import KontanInvestasi
from scraper_engine.sources.idx.scrape_bisnis_com import BisnisMarket
from scraper_engine.sources.idx.scrape_bloomberg_technoz import BloombergTechnoz
from scraper_engine.sources.idx.scrape_gapki import GapkiScraper
from scraper_engine.sources.idx.scrape_idnfinancials import IDNFinancialScraper
from scraper_engine.sources.idx.scrape_icn import ICNScraper
from scraper_engine.sources.idx.scrape_jakartaglobe import JakartaGlobe
from scraper_engine.sources.idx.scrape_jakartapost import JakartaPost
from scraper_engine.sources.sgx.scrape_the_edge_reits import TheEdgeReits
from scraper_engine.config.conf import BRIGHTDATA_API_KEY, BRIGHTDATA_ZONE

import logging
import requests 


LOGGER = logging.getLogger(__name__)


def fetch_with_web_unlocker(
    self,
    target_url: str,
):
    LOGGER.info(
        "[WEB UNLOCKER TEST] Fetching %s",
        target_url,
    )

    try:
        response = requests.post(
            "https://api.brightdata.com/request",
            headers={
                "Authorization": f"Bearer {BRIGHTDATA_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "zone": BRIGHTDATA_ZONE,
                "url": target_url,
                "format": "raw",
                "method": "GET",
            },
            timeout=60,
        )

        LOGGER.info(
            "[WEB UNLOCKER TEST] status=%d url=%s",
            response.status_code,
            target_url,
        )

        if response.status_code != 200:
            LOGGER.warning(
                "[WEB UNLOCKER TEST] Failed body=%s",
                response.text[:500],
            )
            return ""

        return response.text

    except requests.exceptions.RequestException as error:
        LOGGER.error(
            "[WEB UNLOCKER TEST] Request failed for %s: %s",
            target_url,
            error,
        )
        return ""


def test_scrapers():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )

    target_date = "20260921"

    investor_id = InvestorID()
    kontan_investasi = KontanInvestasi()

    investor_id.fetch_news_with_proxy = MethodType(
        fetch_with_web_unlocker,
        investor_id,
    )

    kontan_investasi.fetch_news_with_proxy = MethodType(
        fetch_with_web_unlocker,
        kontan_investasi,
    )

    LOGGER.info("=== Testing Investor ID ===")

    investor_articles = investor_id.extract_news_pages(
        num_pages=1,
        date=target_date,
        is_use_proxy=True,
    )

    LOGGER.info(
        "Investor ID articles: %d",
        len(investor_articles),
    )

    if investor_articles:
        LOGGER.info(
            "Investor ID sample: %s",
            investor_articles[0],
        )

    LOGGER.info("=== Testing Kontan Investasi ===")

    kontan_articles = kontan_investasi.extract_news_pages(
        num_pages=1,
        date=target_date,
        is_use_proxy=True,
    )

    LOGGER.info(
        "Kontan Investasi articles: %d",
        len(kontan_articles),
    )

    if kontan_articles:
        LOGGER.info(
            "Kontan Investasi sample: %s",
            kontan_articles[0],
        )


def fetch_with_scrapling_adapter(
    self,
    url: str,
    wait_selector: str | None = None,
    time_sleep: int = 5,
    retry: bool = True,
):
    scraper = Scraper()
    return scraper.fetch_news_with_scrapling(url)


def test_bisnis():
    scraper = BisnisMarket()

    scraper.fetch_news_with_selenium = MethodType(
        fetch_with_scrapling_adapter,
        scraper,
    )

    articles = scraper.extract_news_pages(
        num_pages=1,
        date="20260921",
    )

    LOGGER.info("articles:", len(articles))

    if articles:
        LOGGER.info(articles[0])


def test_switch__scrapling():
    target_date = "20260921"
    scraper_definitions = [
        ("Bisnis Market", BisnisMarket),
        ("Bloomberg Technoz", BloombergTechnoz),
        # ("GAPKI", GapkiScraper),
        ("IDN Financials", IDNFinancialScraper),
        ("ICN", ICNScraper),
        ("Jakarta Globe", JakartaGlobe),
        ("Jakarta Post", JakartaPost),
        ("The Edge REITs", TheEdgeReits),
    ]

    for scraper_name, scraper_class in scraper_definitions:
        scraper = scraper_class()

        scraper.fetch_news_with_selenium = MethodType(
            fetch_with_scrapling_adapter,
            scraper,
        )
    
        articles = scraper.extract_news_pages(
            num_pages=1,
            date=target_date,
        )

        LOGGER.info(f"{scraper_name} articles:", len(articles))

        if articles:
            LOGGER.info(f"{scraper_name} sample:", articles[0])


if __name__ == "__main__":
    test_switch__scrapling()
