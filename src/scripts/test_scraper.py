from datetime import datetime
from types import MethodType
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup
from scrapling.fetchers import FetcherSession

from scraper_engine.sources.idx.scrape_investor_id import InvestorID
from scraper_engine.sources.idx.scrape_kontan_investasi import KontanInvestasi
from scraper_engine.sources.sgx.scrape_asia_news import AsiaNews
from scraper_engine.sources.sgx.scrape_edgeprop import EdgeProp
from scraper_engine.sources.sgx.scrape_nextinsight import NextInsight
from scraper_engine.sources.sgx.scrape_the_edge import TheEdgeSingapore

import json
import logging


LOGGER = logging.getLogger(__name__)


def log_failed_response(response, url: str):
    response_body = bytes(response.body).decode(
        "utf-8",
        errors="replace",
    )

    LOGGER.warning(
        "[TEST] Non-200 status=%d url=%s",
        response.status,
        url,
    )

    LOGGER.warning(
        "[TEST] Response headers=%s",
        dict(response.headers),
    )

    LOGGER.warning(
        "[TEST] Response body preview=%s",
        response_body[:1000],
    )


def create_soup_fetcher(session: FetcherSession):
    def fetch_with_session(self, url: str):
        LOGGER.info("[TEST] Direct FetcherSession request: %s", url)

        response = session.get(url)

        LOGGER.info(
            "[TEST] status=%d url=%s",
            response.status,
            url,
        )

        if response.status != 200:
            log_failed_response(response, url)
            return None

        return BeautifulSoup(
            bytes(response.body),
            "html.parser",
        )

    return fetch_with_session


def create_text_fetcher(session: FetcherSession):
    def fetch_without_proxy(self, target_url: str):
        LOGGER.info(
            "[TEST] Direct FetcherSession request replacing proxy: %s",
            target_url,
        )

        response = session.get(target_url)

        LOGGER.info(
            "[TEST] status=%d url=%s",
            response.status,
            target_url,
        )

        if response.status != 200:
            log_failed_response(response, target_url)
            return ""

        return bytes(response.body).decode(
            "utf-8",
            errors="replace",
        )

    return fetch_without_proxy


def run_idx_scraper(
    scraper,
    source_name: str,
    target_date: str,
):
    LOGGER.info("=" * 80)
    LOGGER.info("[TEST] Starting IDX source: %s", source_name)
    LOGGER.info("=" * 80)

    try:
        with FetcherSession(
            impersonate="chrome",
            stealthy_headers=True,
            timeout=30,
            retries=1,
        ) as session:
            scraper.fetch_news_with_scrapling = MethodType(
                create_soup_fetcher(session),
                scraper,
            )

            articles = scraper.extract_news_pages(
                num_pages=1,
                date=target_date,
                is_use_proxy=False,
            )

    except Exception:
        LOGGER.exception(
            "[TEST] %s crashed during test",
            source_name,
        )
        return []

    LOGGER.info(
        "[TEST] %s finished with %d article(s)",
        source_name,
        len(articles),
    )

    return articles


def run_sgx_scraper(
    scraper,
    source_name: str,
    target_date: str,
):
    LOGGER.info("=" * 80)
    LOGGER.info("[TEST] Starting SGX source: %s", source_name)
    LOGGER.info("=" * 80)

    try:
        with FetcherSession(
            impersonate="chrome",
            stealthy_headers=True,
            timeout=30,
            retries=1,
        ) as session:
            scraper.fetch_news_with_proxy = MethodType(
                create_text_fetcher(session),
                scraper,
            )

            articles = scraper.extract_news_pages(
                num_pages=1,
                date=target_date,
            )

    except Exception:
        LOGGER.exception(
            "[TEST] %s crashed during test",
            source_name,
        )
        return []

    LOGGER.info(
        "[TEST] %s finished with %d article(s)",
        source_name,
        len(articles),
    )

    return articles


def log_summary(results: dict):
    summary = {
        source_name: {
            "article_count": len(articles),
            "sample": articles[:1],
        }
        for source_name, articles in results.items()
    }

    LOGGER.info(
        "=== TEST SUMMARY ===\n%s",
        json.dumps(
            summary,
            indent=2,
            default=str,
        ),
    )


def test_scrapers():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    idx_date = datetime.now(
        ZoneInfo("Asia/Jakarta"),
    ).strftime("%Y%m%d")

    sgx_date = datetime.now(
        ZoneInfo("Asia/Singapore"),
    ).strftime("%Y%m%d")

    LOGGER.info(
        "[TEST] IDX date=%s SGX date=%s",
        idx_date,
        sgx_date,
    )

    results = {}

    results["investor_id"] = run_idx_scraper(
        scraper=InvestorID(),
        source_name="Investor ID",
        target_date=idx_date,
    )

    results["kontan_investasi"] = run_idx_scraper(
        scraper=KontanInvestasi(),
        source_name="Kontan Investasi",
        target_date=idx_date,
    )

    results["asia_news"] = run_sgx_scraper(
        scraper=AsiaNews(),
        source_name="Asia News",
        target_date=sgx_date,
    )

    results["edgeprop"] = run_sgx_scraper(
        scraper=EdgeProp(),
        source_name="EdgeProp",
        target_date=sgx_date,
    )

    results["nextinsight"] = run_sgx_scraper(
        scraper=NextInsight(),
        source_name="NextInsight",
        target_date=sgx_date,
    )

    results["the_edge_singapore"] = run_sgx_scraper(
        scraper=TheEdgeSingapore(),
        source_name="The Edge Singapore",
        target_date=sgx_date,
    )

    log_summary(results)


if __name__ == "__main__":
    test_scrapers()