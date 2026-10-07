from bs4 import BeautifulSoup
from datetime import datetime
from scrapling.fetchers import StealthySession

from scraper_engine.base.scraper import Scraper

import json
import time
import logging 
import argparse 


LOGGER = logging.getLogger(__name__)


class BCANews(Scraper):
    def __init__(self):
        super().__init__()
        self.stealthy_session_manager = None
        self.stealthy_session = None

    def fetch_with_stealthy_browser(self, url: str):
        # Fallback for when the WAF resets plain HTTP requests. One browser
        # session is reused for the whole run
        try:
            if self.stealthy_session is None:
                self.stealthy_session_manager = StealthySession(
                    headless=True,
                    disable_resources=True,
                )
                self.stealthy_session = self.stealthy_session_manager.__enter__()

            response = self.stealthy_session.fetch(url)

            if response.status != 200:
                LOGGER.warning("[BCA Sekuritas] Stealthy browser got status %d for %s", response.status, url)
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
            LOGGER.error("[BCA Sekuritas] Stealthy browser failed for %s: %s", url, error)
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
            LOGGER.warning("[BCA Sekuritas] Failed to close stealthy session: %s", error)

        finally:
            self.stealthy_session_manager = None
            self.stealthy_session = None

    def fetch_with_fallback(self, url: str):
        soup = self.fetch_news_with_scrapling(url)

        if soup is not None:
            return soup

        LOGGER.info(
            "[BCA Sekuritas] Scrapling failed for %s, trying stealthy browser",
            url
        )
        return self.fetch_with_stealthy_browser(url)

    def extract_json_objects(self, text: str, target_key: str = '"data":'):
        """
        Generator that finds ALL occurrences of `target_key` and extracts 
        the valid JSON structure (Object or Array) immediately following it.
        """
        start_search = 0

        while True:
            # Find the next occurrence of "data":
            start_idx = text.find(target_key, start_search)
            if start_idx == -1:
                break
                
            # Move past the marker
            structure_start = start_idx + len(target_key)
            
            # Find the first opening bracket [ or {
            open_idx = -1
            stack = []
            
            # Scan forward to find start of structure
            for i in range(structure_start, min(structure_start + 50, len(text))):
                char = text[i]
                if char in ['[', '{']:
                    open_idx = i
                    stack.append(char)
                    break
            
            # If no bracket found near marker, skip this occurrence
            if open_idx == -1:
                start_search = structure_start
                continue

            # Count brackets to find the end
            for i in range(open_idx + 1, len(text)):
                char = text[i]
                
                if char == '[': stack.append('[')
                elif char == '{': stack.append('{')
                elif char == ']':
                    if stack and stack[-1] == '[': stack.pop()
                elif char == '}':
                    if stack and stack[-1] == '{': stack.pop()
                
                if not stack:
                    # Found the closing bracket
                    json_str = text[open_idx : i+1]
                    yield json_str
                    # Continue searching after this object
                    start_search = i + 1
                    break
            else:
                # If loop finishes without empty stack, structure is malformed/incomplete
                start_search = structure_start

    def format_iso_date(self, iso_str: str) -> str:
        if not iso_str: return ""
        try:
            dt = datetime.fromisoformat(iso_str.replace('Z', '+00:00'))
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        
        except ValueError:
            return iso_str
        
    def fetch_article_list(self, page_number: int) -> list:
        target_url = f"https://bcasekuritas.co.id/en/latest-news/news?page={page_number}"

        soup = self.fetch_with_fallback(target_url)

        if soup is None:
            LOGGER.error("[BCA Sekuritas] Failed to load news page %d.", page_number)
            return []

        # The article list is embedded in the Next.js flight payload
        for script in soup.find_all("script"):
            content = script.string or ""

            if "self.__next_f.push" in content and "current_page" in content:
                clean_content = content.replace('\\"', '"').replace('\\\\', '\\')

                for json_str in self.extract_json_objects(clean_content, '"data":'):
                    try:
                        parsed_data = json.loads(json_str)

                        if (
                            isinstance(parsed_data, list)
                            and len(parsed_data) > 0
                            and ("slug" in parsed_data[0] or "title_id" in parsed_data[0])
                        ):
                            LOGGER.info("[BCA Sekuritas] Target JSON data found.")
                            return parsed_data
                        
                    except json.JSONDecodeError:
                        continue

        LOGGER.info("[BCA Sekuritas] JSON extraction failed")
        return []

    def parse_articles(self, article_items: list, target_date: str) -> tuple[list, bool]:
        parsed_articles = []
        reached_older_date = False

        target_datetime = datetime(
            int(target_date[:4]),
            int(target_date[4:6]),
            int(target_date[6:]),
        )

        for article_item in article_items:
            if isinstance(article_item, dict):
                title = article_item.get("title_en") or article_item.get("title_id")
                slug = article_item.get("slug", "")
                source_url = f"https://bcasekuritas.co.id/en/latest-news/news/{slug}"
                published_at = self.format_iso_date(article_item.get("published_at"))

            if not published_at:
                LOGGER.info("[BCA Sekuritas] Failed to parse date for url: %s. Skipping.", source_url)
                continue

            article_datetime = datetime.strptime(published_at[:10], "%Y-%m-%d")

            if article_datetime < target_datetime:
                reached_older_date = True
                break

            if not source_url:
                continue
            
            parsed_articles.append({
                "title": title,
                "source": source_url,
                "timestamp": published_at,
                "thumbnail": None  # have no thumnail on their site 
            })

        return parsed_articles, reached_older_date

    def extract_news_pages(self, num_pages: int, date: str) -> list:
        try:
            page_number = 1

            while True:
                LOGGER.info("[BCA Sekuritas] Scraping page %d.", page_number)

                article_items = self.fetch_article_list(page_number)

                if not article_items:
                    LOGGER.info("[BCA Sekuritas] No articles found on page %d, stopping.", page_number)
                    break

                articles, reached_older_date = self.parse_articles(article_items, date)

                self.articles.extend(articles)
                LOGGER.info("[BCA Sekuritas] Page %d: %d articles collected.", page_number, len(articles))

                if reached_older_date:
                    LOGGER.info("[BCA Sekuritas] Reached articles older than %s, stopping.", date)
                    break

                if num_pages is not None and page_number >= num_pages:
                    break

                page_number += 1
                time.sleep(1.5)

        finally:
            self.close_stealthy_session()

        LOGGER.info("[BCA Sekuritas] Total scraped: %d", len(self.articles))
        return self.articles


def main():
    scraper = BCANews()

    parser = argparse.ArgumentParser(description="Script for scraping data from BCA Sekuritas")
    parser.add_argument("date", type=str)
    parser.add_argument("filename", type=str, nargs="?", default="bcasekuritas")
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
    uv run -m src.scraper_engine.sources.idx.scrape_bca_news <date> [filename] [--pages N] [--csv]

    Examples:
    uv run -m src.scraper_engine.sources.idx.scrape_bca_news 20260427
    uv run -m src.scraper_engine.sources.idx.scrape_bca_news 20260427 test_bca
    uv run -m src.scraper_engine.sources.idx.scrape_bca_news 20260427 test_bca --pages 3 --csv
    """
    main()
