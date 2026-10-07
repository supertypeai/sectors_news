from datetime import datetime
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup, XMLParsedAsHTMLWarning
from scrapling.fetchers import StealthySession

from scraper_engine.base.scraper import Scraper

import argparse
import logging
import warnings


LOGGER = logging.getLogger(__name__)

# The sitemap is parsed with html.parser, which keeps every field we need
warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)

# Google News sitemap: the last 48 hours of articles with title, publish
# time and image, so one request replaces the listing pages and the
# per-article timestamp fetches
SITEMAP_URL = "https://money.kompas.com/sitemap-news-money.xml"

AWS_WAF_CHALLENGE_MARKER = "awsWafCookieDomainList"

WIB = ZoneInfo("Asia/Jakarta")


class KompasMoney(Scraper):
    def __init__(self):
        super().__init__()
        self.stealthy_session_manager = None
        self.stealthy_session = None

    def fetch_with_stealthy_browser(self, url: str):
        # Kompas sits behind an AWS WAF JS challenge (status 202) that plain
        # HTTP clients cannot pass, so let a stealth browser run it
        try:
            if self.stealthy_session is None:
                self.stealthy_session_manager = StealthySession(
                    headless=True,
                    network_idle=True,
                )
                self.stealthy_session = self.stealthy_session_manager.__enter__()

            response = self.stealthy_session.fetch(url)
            body = bytes(response.body)

            if response.status != 200 or AWS_WAF_CHALLENGE_MARKER.encode() in body:
                LOGGER.warning("[Kompas Money] Stealthy browser got status %d for %s", response.status, url)
                self.record_request_failure(
                    url=url,
                    reason="HTTPStatusError",
                    status_code=response.status,
                    message=f"Received status code {response.status}",
                )
                return None

            self.record_request_success(status_code=response.status)
            return BeautifulSoup(body, "html.parser")

        except Exception as error:
            LOGGER.error("[Kompas Money] Stealthy browser failed for %s: %s", url, error)
            self.record_request_failure(
                url=url,
                reason=type(error).__name__,
                message=str(error),
            )
            return None

    def close_stealthy_session(self) -> None:
        if self.stealthy_session_manager is None:
            return

        try:
            self.stealthy_session_manager.__exit__(None, None, None)

        except Exception as error:
            LOGGER.warning("[Kompas Money] Failed to close stealthy session: %s", error)

        finally:
            self.stealthy_session_manager = None
            self.stealthy_session = None

    def fetch_with_fallback(self, url: str):
        soup = self.fetch_news_with_scrapling(url)

        if soup is not None:
            return soup

        LOGGER.info(
            "[Kompas Money] Scrapling failed for %s, trying stealthy browser",
            url
        )
        soup = self.fetch_with_stealthy_browser(url)

        if soup is not None:
            return soup

        LOGGER.info(
            "[Kompas Money] Stealthy browser failed for %s, falling back to Web Unlocker",
            url
        )
        return self.fetch_news_with_web_unlocker(url)

    def parse_date(self, raw_date: str) -> str:
        if not raw_date:
            return None

        try:
            published_at = datetime.fromisoformat(raw_date).astimezone(WIB)
            return published_at.strftime("%Y-%m-%d %H:%M:%S")

        except ValueError:
            return None

    def parse_sitemap(self, soup: BeautifulSoup, date: str) -> list:
        parsed_articles = []

        for url_tag in soup.find_all("url"):
            loc_tag = url_tag.find("loc")
            title_tag = url_tag.find("news:title")
            date_tag = url_tag.find("news:publication_date")
            image_tag = url_tag.find("image:loc")

            if not loc_tag or not title_tag or not date_tag:
                continue

            published_at = self.parse_date(date_tag.get_text(strip=True))

            if not published_at:
                LOGGER.info("[Kompas Money] Failed to parse date for url: %s. Skipping.", loc_tag.get_text(strip=True))
                continue

            # The sitemap covers two days, so keep only the requested one
            if published_at[:10].replace("-", "") != date:
                continue

            parsed_articles.append({
                "title": title_tag.get_text(strip=True),
                "source": loc_tag.get_text(strip=True),
                "thumbnail": image_tag.get_text(strip=True) if image_tag else None,
                "timestamp": published_at,
            })

        return parsed_articles

    def extract_news_pages(self, num_pages: int, date: str):
        # num_pages is unused: the sitemap is a single document
        try:
            soup = self.fetch_with_fallback(SITEMAP_URL)
        finally:
            self.close_stealthy_session()

        if not soup:
            LOGGER.info("[Kompas Money] Failed to fetch sitemap, stopping.")
            return self.articles

        articles = self.parse_sitemap(soup, date)
        self.articles.extend(articles)

        LOGGER.info("[Kompas Money] Total scraped: %d", len(self.articles))
        return self.articles


def main():
    scraper = KompasMoney()

    parser = argparse.ArgumentParser(description="Script for scraping data from Kompas Money")
    parser.add_argument("date", type=str)
    parser.add_argument("filename", type=str, nargs="?", default="kompasmoney")
    parser.add_argument("--pages", type=int, default=None, help="Unused, kept for the shared scraper interface")
    parser.add_argument("--csv", action="store_true", help="Flag to indicate write to csv file")

    args = parser.parse_args()

    scraper.extract_news_pages(args.pages, args.date)
    scraper.write_json(scraper.articles, args.filename)

    if args.csv:
        scraper.write_csv(scraper.articles, args.filename)


if __name__ == "__main__":
    """
    How to run:
    uv run -m src.scraper_engine.sources.idx.scrape_kompas <date> [filename] [--csv]

    Examples:
    uv run -m src.scraper_engine.sources.idx.scrape_kompas 20260427
    uv run -m src.scraper_engine.sources.idx.scrape_kompas 20260427 test_kompas --csv
    """
    main()
