import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.common.exceptions import WebDriverException
from datetime import datetime
from urllib.parse import urlparse

from scraper_engine.base.scraper import get_chrome_info
from scraper_engine.config.conf import PROXY
from scraper_engine.base.scraper import Scraper

import json
import time
import random
import platform
import logging 
import shutil 
import os 
import zipfile
import tempfile
import argparse 


LOGGER = logging.getLogger(__name__)


class BCANews(Scraper):
    def create_proxy_extension(self, proxy_url: str) -> str:
        """
        Parses a proxy URL and generates an extension ZIP.
        """
        parsed = urlparse(proxy_url)
        
        # Extract components
        scheme = parsed.scheme or "http"
        host = parsed.hostname
        port = parsed.port
        user = parsed.username
        password = parsed.password

        manifest_json = """
        {
            "version": "1.0.0",
            "manifest_version": 2,
            "name": "Proxy Auth Extension",
            "permissions": [
                "proxy",
                "tabs",
                "unlimitedStorage",
                "storage",
                "<all_urls>",
                "webRequest",
                "webRequestBlocking"
            ],
            "background": {
                "scripts": ["background.js"]
            },
            "minimum_chrome_version": "22.0.0"
        }
        """

        background_js = f"""
        var proxy_config = {{
            mode: "fixed_servers",
            rules: {{
                singleProxy: {{
                    scheme: "{scheme}",
                    host: "{host}",
                    port: parseInt({port})
                }},
                bypassList: ["localhost"]
            }}
        }};

        chrome.proxy.settings.set({{value: proxy_config, scope: "regular"}}, function() {{}});

        function handle_auth(details) {{
            return {{
                authCredentials: {{
                    username: "{user}",
                    password: "{password}"
                }}
            }};
        }}

        chrome.webRequest.onAuthRequired.addListener(
            handle_auth,
            {{urls: ["<all_urls>"]}},
            ['blocking']
        );
        """

        extension_path = os.path.join(tempfile.gettempdir(), f"proxy_auth_{host}_{port}.zip")

        with zipfile.ZipFile(extension_path, 'w') as extension_zip:
            extension_zip.writestr("manifest.json", manifest_json)
            extension_zip.writestr("background.js", background_js)

        return extension_path

    def navigate_with_retry(self, driver, url: str, max_retries: int = 3) -> bool:
        """
        Tries to navigate to a URL. If the WAF resets the connection, 
        waits and retries.
        """
        for attempt in range(max_retries):
            try:
                LOGGER.info(f"Navigating to {url} (Attempt {attempt + 1}/{max_retries})")
                driver.get(url)
                return True 
            
            except WebDriverException as error:
                if "ERR_CONNECTION_RESET" in str(error) or "ERR_CONNECTION_CLOSED" in str(error):
                    LOGGER.warning(f"Connection reset by WAF. Sleeping 10s before retry")
                    time.sleep(10) 
                    continue

                else:
                    raise error
                
        return False

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
        
    def setup_driver(self):
        options = uc.ChromeOptions()
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1920,1080")
        options.add_argument(
            "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--ignore-certificate-errors")
        options.add_argument("--allow-running-insecure-content")

        if PROXY:
            parsed_proxy = urlparse(PROXY)
            if parsed_proxy.username and parsed_proxy.password:
                extension_path = self.create_proxy_extension(PROXY)
                options.add_extension(extension_path)

            else:
                options.add_argument(f"--proxy-server={PROXY}")

        chrome_version, chrome_path = get_chrome_info()
        driver_path = shutil.which("chromedriver")

        return uc.Chrome(
            options=options,
            use_subprocess=True,
            version_main=chrome_version,
            browser_executable_path=chrome_path,
            driver_executable_path=driver_path if platform.system() == "Linux" else None,
        )

    def fetch_article_list(self, driver, page_number: int) -> list:
        if not self.navigate_with_retry(driver, "https://bcasekuritas.co.id/"):
            LOGGER.error("[BCA Sekuritas] Failed to load homepage after retries.")
            return []

        time.sleep(random.uniform(3, 5))

        target_url = f"https://bcasekuritas.co.id/en/latest-news/news?page={page_number}"

        if not self.navigate_with_retry(driver, target_url):
            LOGGER.error("[BCA Sekuritas] Failed to load news page after retries.")
            return []

        time.sleep(8)

        scripts = driver.find_elements(By.TAG_NAME, "script")

        for script in scripts:
            content = script.get_attribute("innerHTML")
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
        return driver.find_elements(By.CSS_SELECTOR, "div.bg-card")

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
            driver = self.setup_driver()

        except Exception as error:
            LOGGER.error("[BCA Sekuritas] Failed to initialize driver: %s", error)
            return []

        try:
            page_number = 1

            while True:
                LOGGER.info("[BCA Sekuritas] Scraping page %d.", page_number)

                article_items = self.fetch_article_list(driver, page_number)

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
            try:
                driver.quit()

            except Exception:
                pass

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