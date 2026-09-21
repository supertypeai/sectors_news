from types import MethodType

from scraper_engine.base.scraper import Scraper
from scraper_engine.sources.idx.scrape_investor_id import InvestorID
from scraper_engine.sources.idx.scrape_kontan_investasi import KontanInvestasi
from scraper_engine.sources.idx.scrape_bisnis_com import BisnisMarket
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

    print("articles:", len(articles))

    if articles:
        print(articles[0])


if __name__ == "__main__":
    test_bisnis()