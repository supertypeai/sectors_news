from types import MethodType
from dotenv import load_dotenv

from scraper_engine.sources.idx.scrape_investor_id import InvestorID
from scraper_engine.sources.idx.scrape_kontan_investasi import KontanInvestasi

import logging
import os
import requests


load_dotenv()

LOGGER = logging.getLogger(__name__)


def fetch_with_web_unlocker(
    self,
    target_url: str,
):
    api_key = os.getenv("BRIGHTDATA_API_KEY")
    zone = os.getenv(
        "BRIGHTDATA_ZONE",
    )

    LOGGER.info(
        "[WEB UNLOCKER TEST] Fetching %s",
        target_url,
    )

    try:
        response = requests.post(
            "https://api.brightdata.com/request",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "zone": zone,
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


if __name__ == "__main__":
    test_scrapers()