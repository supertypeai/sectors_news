from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup
from scrapling.fetchers import StealthySession

from scraper_engine.base.scraper import Scraper
from scraper_engine.sources.utils.constant import INDONESIAN_MONTHS

import argparse
import re
import time
import logging 


LOGGER = logging.getLogger(__name__)

WIB = ZoneInfo("Asia/Jakarta")

# Article URLs carry the publish date, e.g. /read/20261016/7/2013091/...
# and photo pages use /view/20261016/...
URL_DATE_PATTERN = re.compile(r"/(?:read|view)/(\d{8})/")

RELATIVE_UNITS = {
    "detik": "seconds",
    "menit": "minutes",
    "jam": "hours",
}


class BisnisMarket(Scraper):
    def __init__(self):
        super().__init__()
        self.stealthy_session_manager = None
        self.stealthy_session = None

    def fetch_with_stealthy_browser(self, url: str):
        # Article pages sit behind a Cloudflare JS challenge that plain HTTP
        # clients cannot pass, so solve it in a stealth browser. One browser
        # session is reused for the whole run. No network_idle: the page's ads
        # never go idle, so each fetch waited out the timeout (~2 min instead
        # of ~5 s), and the publish date is in the HTML on load
        try:
            if self.stealthy_session is None:
                self.stealthy_session_manager = StealthySession(
                    headless=True,
                    solve_cloudflare=True,
                    network_idle=False,
                )
                self.stealthy_session = self.stealthy_session_manager.__enter__()

            response = self.stealthy_session.fetch(url)

            if response.status != 200:
                LOGGER.warning("[Bisnis Market] Stealthy browser got status %d for %s", response.status, url)
                self.record_request_failure(
                    url=url,
                    reason="HTTPStatusError",
                    status_code=response.status,
                    message=f"Received status code {response.status}",
                )
                return None

            self.record_request_success(status_code=response.status)
            return BeautifulSoup(bytes(response.body), "html.parser")

        except Exception as error:
            LOGGER.error("[Bisnis Market] Stealthy browser failed for %s: %s", url, error)
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
            LOGGER.warning("[Bisnis Market] Failed to close stealthy session: %s", error)
        
        finally:
            self.stealthy_session_manager = None
            self.stealthy_session = None

    def fetch_with_fallback(self, url: str):
        soup = self.fetch_news_with_scrapling(url)

        if soup is not None:
            return soup

        LOGGER.info(
            "[Bisnis Market] Scrapling failed for %s, trying stealthy browser", 
            url
        )
        soup = self.fetch_with_stealthy_browser(url)

        if soup is not None:
            return soup

        LOGGER.info(
            "[Bisnis Market] Stealthy browser failed for %s, falling back to Web Unlocker", 
            url
        )
        return self.fetch_news_with_web_unlocker(url)

    def fetch_article_list(self, url):
        soup = self.fetch_with_fallback(url)
        
        if not soup:
            LOGGER.info("[Bisnis Market] [FAIL] Failed to fetch HTML or timed out for %s", url)
            return []
        
        article_container = soup.find("div", id="indeksListView")

        if not article_container:
            LOGGER.info("[Bisnis Market] [FAIL] Target container 'indeksListView' not found.")
            return []
        
        articles_items = article_container.find_all("div", class_="artItem")

        return articles_items

    def fetch_article_timestamp(self, article_url: str) -> str:
        soup = self.fetch_with_fallback(article_url)

        if not soup:
            return None

        LOGGER.info("[Bisnis Market] Page source length: %d", len(str(soup)))
        date_tag = soup.select_one("div.detailsAttributeDates")

        if not date_tag:
            return None

        return self.parse_absolute_date(date_tag.get_text(strip=True))

    def parse_articles(self, article_items: list) -> list:
        parsed_articles = []

        for article_item in article_items:
            link_tag = article_item.find("a", class_="artLink")
            title_tag = article_item.find("h4", class_="artTitle")
            date_tag = article_item.find("div", class_="artDate")

            if not link_tag or not title_tag or not date_tag:
                continue

            source_url = link_tag.get("href")
            title = title_tag.get_text(strip=True)
            raw_date = date_tag.get_text(strip=True)

            thumbnail_tag = article_item.select_one("div.artImg img")
            thumbnail_url = thumbnail_tag["src"] if thumbnail_tag else None

            if thumbnail_url and "images.bisnis.com/thumb/" in thumbnail_url:
                thumbnail_url = thumbnail_url.split("?", 1)[0] + "?w=1920&h=1080"

            if "yang lalu" in raw_date:
                # Relative labels truncate hours, so read the exact time from the
                # article page. Only the first fetch is slow (it solves Cloudflare),
                # later ones reuse the session. Fall back to the label if it fails
                published_at = self.fetch_article_timestamp(source_url)
                time.sleep(0.5)

                if not published_at:
                    published_at = self.parse_relative_date(raw_date)

            else:
                published_at = self.parse_absolute_date(raw_date)

            if not published_at:
                LOGGER.info("[Bisnis Market] Failed to parse date for url: %s. Skipping.", source_url)
                continue
            
            parsed_articles.append({
                "title": title,
                "source": source_url,
                "thumbnail": thumbnail_url,
                "timestamp": published_at,
            })

        return parsed_articles
    
    def parse_relative_date(self, raw_date: str) -> str | None:
        # "20 menit yang lalu" or "2 jam yang lalu". Hours are truncated by the
        # site, so the result can be up to 59 minutes later than the real time
        parts = raw_date.split()

        if len(parts) < 2 or parts[1] not in RELATIVE_UNITS:
            return None

        try:
            amount = int(parts[0])

        except ValueError:
            return None

        published_at = datetime.now(WIB) - timedelta(
            **{RELATIVE_UNITS[parts[1]]: amount}
        )

        return published_at.strftime("%Y-%m-%d %H:%M:%S")

    def parse_absolute_date(self, raw_date: str) -> str:
        if not raw_date:
            return None

        try:
            cleaned = raw_date.strip()

            if "," in cleaned:
                cleaned = cleaned.split(", ", 1)[-1]

            cleaned = cleaned.replace("WIB", "").strip()
            date_parts = cleaned.split("|")

            if len(date_parts) != 2:
                return None

            date_part = date_parts[0].strip()
            time_part = date_parts[1].strip()

            parts = date_part.split()
            day = int(parts[0])
            month = INDONESIAN_MONTHS.get(parts[1])
            year = int(parts[2])

            if not month:
                return None

            hour, minute = time_part.split(":")
            parsed_date = datetime(year, month, day, int(hour), int(minute))

            return parsed_date.strftime("%Y-%m-%d %H:%M:%S")

        except (ValueError, IndexError, AttributeError) as error:
            LOGGER.error("[Bisnis Market] Error parsing date '%s': %s", raw_date, error)
            return None

    def get_url_date(self, article_item) -> str | None:
        link_tag = article_item.find("a", class_="artLink")
        
        match = URL_DATE_PATTERN.search(
            link_tag.get("href", "")
        ) if link_tag else None

        return match.group(1) if match else None

    def extract_news_pages(self, num_pages: int, date: str) -> list:
        # The site ignores the page param when a date param is present, so
        # page through the undated index (newest first) and filter by the
        # date in each article URL, which is exact unlike relative labels
        market_url = "https://www.bisnis.com/index?categoryId=194&type=indeks&"
        finance_url = "https://www.bisnis.com/index?categoryId=5&type=indeks&"

        seen_urls = set()

        try:
            for url in [market_url, finance_url]:
                page_number = 1
                seen_page_urls = set()

                while True:
                    page_url = url + f"page={page_number}"
                
                    article_items = self.fetch_article_list(page_url)

                    if not article_items:
                        LOGGER.info(
                            "[Bisnis Market] No articles found on page %d, stopping.", 
                            page_number
                        )
                        break

                    url_dates = [
                        self.get_url_date(item) 
                        for item in article_items
                    ]

                    known_dates = [
                        url_date 
                        for url_date in url_dates 
                        if url_date
                    ]

                    if known_dates and all(
                        url_date < date 
                        for url_date in known_dates
                    ):
                        LOGGER.info(
                            "[Bisnis Market] Page %d is older than %s, stopping.", 
                            page_number, 
                            date
                        )
                        break

                    page_urls = {
                        item.find("a", class_="artLink").get("href")
                        for item in article_items
                        if item.find("a", class_="artLink")
                    }

                    if page_urls <= seen_page_urls:
                        LOGGER.info(
                            "[Bisnis Market] Page %d returned duplicate articles, stopping.", 
                            page_number
                        )
                        break

                    seen_page_urls.update(page_urls)

                    target_items = [
                        item 
                        for item, url_date in zip(
                            article_items, url_dates
                        )
                        if url_date == date
                    ]

                    articles = self.parse_articles(target_items)

                    new_articles = [
                        article for article in articles 
                        if article.get('source') not in seen_urls
                    ]

                    for article in articles: 
                        seen_urls.add(article.get('source'))

                    self.articles.extend(new_articles)

                    LOGGER.info(
                        "[Bisnis Market] Page %d: %d articles collected.", 
                        page_number, 
                        len(new_articles)
                    )

                    if num_pages is not None and page_number >= num_pages:
                        break

                    page_number += 1
                    time.sleep(1)
        finally:
            self.close_stealthy_session()

        LOGGER.info("[Bisnis Market] Total scraped: %d", len(self.articles))
        return self.articles


def main():
    scraper = BisnisMarket()

    parser = argparse.ArgumentParser(description="Script for scraping data from Bisnis Market")
    parser.add_argument("date", type=str)
    parser.add_argument("filename", type=str, nargs="?", default="bisnismarket")
    parser.add_argument("--pages", type=int, default=None, help="Number of pages to scrape (default: all)")
    parser.add_argument("--csv", action="store_true", help="Flag to indicate write to csv file")

    args = parser.parse_args()

    scraper.extract_news_pages(args.pages, args.date)
    scraper.write_json(scraper.articles, args.filename)

    if args.csv:
        scraper.write_csv(scraper.articles, args.filename)


if __name__ == "__main__":
    """
    How to run:
    uv run -m src.scraper_engine.sources.idx.scrape_bisnis_com <date> [filename] [--pages N] [--csv]

    Examples:
    uv run -m src.scraper_engine.sources.idx.scrape_bisnis_com 20260427
    uv run -m src.scraper_engine.sources.idx.scrape_bisnis_com 20260427 test_bisnis_market
    uv run -m src.scraper_engine.sources.idx.scrape_bisnis_com 20260427 test_bisnis_market --pages 3 --csv
    """
    main()
