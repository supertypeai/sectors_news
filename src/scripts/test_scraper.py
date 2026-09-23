from types import MethodType
from urllib.parse import urlparse

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
from scraper_engine.preprocessing.article_fetcher import get_article_body

import logging
import requests 


LOGGER = logging.getLogger(__name__)


def test_scrapers():
    target_date = "20260921"

    investor_id = InvestorID()
    kontan_investasi = KontanInvestasi()

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


def test_switch__scrapling():
    target_date = "20260921"
    scraper_definitions = [
        ("Bisnis Market", BisnisMarket),
        ("Bloomberg Technoz", BloombergTechnoz),
        # ("GAPKI", GapkiScraper),
        ("IDN Financials", IDNFinancialScraper),
        ("ICN", ICNScraper),
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


def test_jakarta_globe_web_unlocker():
    scraper = JakartaGlobe()

    articles = scraper.extract_news_pages(
        num_pages=1,
        date="20260921",
    )

    LOGGER.info(
        "Jakarta Globe articles: %d",
        len(articles),
    )

    if articles:
        LOGGER.info(
            "Jakarta Globe sample: %s",
            articles[0],
        )


def test_investorid_article_fetcher(urls: list[str]):
    for url in urls:
        domain = urlparse(url).netloc

        article = get_article_body(
            url=url
        )

        LOGGER.info(
            "\nCheck domain: %s | text: %s", domain, article[:500]
        )


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )

    # test_switch__scrapling()
    test_jakarta_globe_web_unlocker()

    urls = [
        "https://investor.id/market/455147/memperbesar-peluangnormalisasi-treatment-msci",
        "https://jakartaglobe.id/business/two-years-into-prabowo-presidency-economists-question-quality-of-economic-growth"
    ]
    test_investorid_article_fetcher(urls=urls)
