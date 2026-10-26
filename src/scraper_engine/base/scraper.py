from bs4 import BeautifulSoup

from scrapling.fetchers import FetcherSession

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config.env import (
    PROXY, 
    BRIGHTDATA_API_KEY, 
    BRIGHTDATA_ZONE,
    SCRAPINGANT_API_KEY
)
from scraper_engine.config.conf import (
    USER_AGENT, 
    HEADERS_SCRAPER, 
    CRAWLER_USER_AGENT,
    FETCH_CONCURRENCY,
    SCRAPINGANT_CONFLICT_RETRIES,
)
from scraper_engine.utils.json_helpers import (
    write_csv as write_csv_file,
    write_json as write_json_file,
)

import requests
import logging 
import threading
import time


LOGGER = logging.getLogger(__name__)

# Articles are fetched in threads, and += on the health counters is not atomic
HEALTH_LOCK = threading.Lock()


class Scraper:
    soup: BeautifulSoup
    articles: list
    proxy: str | None

    def __init__(self):
        self.articles = []

        self.session = requests.Session()

        retry = Retry(
            total=3,
            backoff_factor=2,
        )

        adapter = HTTPAdapter(
            max_retries=retry,
        )

        self.session.mount(
            "http://",
            adapter,
        )

        self.session.mount(
            "https://",
            adapter,
        )

        self.scrapling_session_manager = None
        self.scrapling_session = None
        self.reset_health()

    def reset_health(self) -> None:
        self.health = {
            "requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "http_statuses": [],
            "failures": [],
        }

    def record_request_success(
        self,
        status_code: int | None = None,
    ) -> None:
        with HEALTH_LOCK:
            self.health["requests"] += 1
            self.health["successful_requests"] += 1

            if status_code is not None:
                self.health["http_statuses"].append(status_code)

    def record_request_failure(
        self,
        url: str,
        reason: str,
        status_code: int | None = None,
        message: str | None = None,
    ) -> None:
        with HEALTH_LOCK:
            self.health["requests"] += 1
            self.health["failed_requests"] += 1

            if status_code is not None:
                self.health["http_statuses"].append(status_code)

            self.health["failures"].append({
                "stage": "fetch",
                "url": url,
                "status": status_code,
                "reason": reason,
                "message": message,
            })

    def fetch_news(self, url):
        response = None

        try:
            response = self.session.get(
                url,
                headers=HEADERS_SCRAPER,
                timeout=10,
            )

            if response.status_code != 200:
                LOGGER.warning(
                    "Non-200 status %d for %s",
                    response.status_code,
                    url,
                )
                self.record_request_failure(
                    url=url,
                    reason="HTTPStatusError",
                    status_code=response.status_code,
                    message=f"Received status code {response.status_code}",
                )
                return None

            self.soup = BeautifulSoup(
                response.content,
                "html.parser",
            )

            self.record_request_success(
                status_code=response.status_code,
            )

            return self.soup

        except Exception as error:
            LOGGER.error(
                "Error fetching the URL: %s",
                error,
            )
            self.record_request_failure(
                url=url,
                reason=type(error).__name__,
                status_code=(
                    response.status_code
                    if response is not None
                    else None
                ),
                message=str(error),
            )
            return None

    def _get_scrapling_session(self):
        if self.scrapling_session is None:
            LOGGER.info(
                "Initializing Scrapling FetcherSession for %s",
                self.__class__.__name__,
            )

            self.scrapling_session_manager = FetcherSession(
                impersonate="chrome",
                stealthy_headers=True,
                timeout=30,
                retries=3,
            )

            self.scrapling_session = (
                self.scrapling_session_manager.__enter__()
            )

        return self.scrapling_session

    def fetch_news_with_scrapling(
        self,
        url: str,
    ):
        response = None

        try:
            scrapling_session = self._get_scrapling_session()

            response = scrapling_session.get(url)

            if response.status != 200:
                body_preview = bytes(response.body).decode(
                    "utf-8",
                    errors="replace",
                )
                LOGGER.warning(
                    "Non-200 status %d for %s; response body preview: %r",
                    response.status,
                    url,
                    body_preview,
                )
                self.record_request_failure(
                    url=url,
                    reason="HTTPStatusError",
                    status_code=response.status,
                    message=f"Received status code {response.status}",
                )
                return None

            soup = BeautifulSoup(
                bytes(response.body),
                "html.parser",
            )

            self.record_request_success(
                status_code=response.status,
            )

            return soup

        except Exception as error:
            LOGGER.error(
                "Scrapling request failed for %s: %s",
                url,
                error,
            )
            self.record_request_failure(
                url=url,
                reason=type(error).__name__,
                status_code=(
                    response.status
                    if response is not None
                    else None
                ),
                message=str(error),
            )
            return None

    def close_scrapling_session(self) -> None:
        if self.scrapling_session_manager is None:
            return

        LOGGER.info(
            "Closing Scrapling FetcherSession for %s",
            self.__class__.__name__,
        )

        try:
            self.scrapling_session_manager.__exit__(
                None,
                None,
                None,
            )

        except Exception as error:
            LOGGER.warning(
                "Failed to close Scrapling session for %s: %s",
                self.__class__.__name__,
                error,
            )

        finally:
            self.scrapling_session = None
            self.scrapling_session_manager = None

    def fetch_news_with_web_unlocker(
        self,
        target_url: str,
    ):
        response = None

        try:
            response = requests.post(
                "https://api.brightdata.com/request",
                headers={
                    "Authorization": (
                        f"Bearer {BRIGHTDATA_API_KEY}"
                    ),
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

            if response.status_code != 200:
                LOGGER.warning(
                    "Web Unlocker returned status %d for %s",
                    response.status_code,
                    target_url,
                )
                self.record_request_failure(
                    url=target_url,
                    reason="HTTPStatusError",
                    status_code=response.status_code,
                    message=f"Received status code {response.status_code}",
                )
                return None

            # Bright Data reports its own failures (quota, denylisted IP, a site
            # it could not unlock) as a 200 with an empty body and the real
            # status in x-brd-* headers, so treat those as failures and let
            # ScrapingAnt take over
            brightdata_error = response.headers.get("x-brd-error")

            if brightdata_error or not response.content:
                brightdata_status = response.headers.get("x-brd-status-code")
                LOGGER.warning(
                    "Web Unlocker failed for %s: %s (status %s)",
                    target_url,
                    brightdata_error or "empty body",
                    brightdata_status,
                )
                self.record_request_failure(
                    url=target_url,
                    reason="WebUnlockerError",
                    status_code=(
                        int(brightdata_status)
                        if brightdata_status and brightdata_status.isdigit()
                        else response.status_code
                    ),
                    message=response.headers.get("x-brd-err-msg") or brightdata_error or "Empty body",
                )
                return None

            soup = BeautifulSoup(
                response.text,
                "html.parser",
            )

            self.record_request_success(
                status_code=response.status_code,
            )

            return soup

        except Exception as error:
            LOGGER.error(
                "Web Unlocker request failed for %s: %s",
                target_url,
                error,
            )
            self.record_request_failure(
                url=target_url,
                reason=type(error).__name__,
                status_code=(
                    response.status_code
                    if response is not None
                    else None
                ),
                message=str(error),
            )
            return None

    def fetch_news_with_scrapingant(self, target_url: str):
        response = None

        try:
            # parallel article fetches can hit, so wait for a slot and retry
            for attempt in range(SCRAPINGANT_CONFLICT_RETRIES + 1):
                response = requests.get(
                    "https://api.scrapingant.com/v2/general",
                    params={
                        "url": target_url,
                        "x-api-key": SCRAPINGANT_API_KEY,
                        "browser": "false",
                    },
                    timeout=60,
                )

                if response.status_code != 409 or attempt == SCRAPINGANT_CONFLICT_RETRIES:
                    break

                time.sleep(2 ** attempt)

            if response.status_code != 200:
                LOGGER.warning(
                    "ScrapingAnt returned status %d for %s",
                    response.status_code,
                    target_url,
                )
                self.record_request_failure(
                    url=target_url,
                    reason="HTTPStatusError",
                    status_code=response.status_code,
                    message=f"Received status code {response.status_code}",
                )
                return None

            self.record_request_success(
                status_code=response.status_code
            )

            return BeautifulSoup(
                response.content, 
                "html.parser"
            )

        except Exception as error: 
            LOGGER.error(
                "ScrapingAnt request failed for %s: %s",
                target_url,
                error,
            )
            self.record_request_failure(
                url=target_url,
                reason=type(error).__name__,
                status_code=(
                    response.status_code
                    if response is not None
                    else None
                ),
                message=str(error),
            )
            return None 
    
    def fetch_news_with_fallback(self, target_url: str):
        soup = self.fetch_news_with_scrapingant(target_url)

        if soup is not None:
            return soup

        LOGGER.warning(
            "ScrapingAnt failed for %s, falling back to brightdata",
            target_url,
        )
        
        return self.fetch_news_with_web_unlocker(target_url)

    def fetch_many_with_fallback(
        self,
        urls: list[str],
    ) -> dict[str, BeautifulSoup | None]:
        # Each URL through fetch_news_with_fallback, FETCH_CONCURRENCY at a time,
        # keyed by URL with None for a page neither service returned
        unique_urls = list(dict.fromkeys(url for url in urls if url))

        if not unique_urls:
            return {}

        with ThreadPoolExecutor(
            max_workers=min(FETCH_CONCURRENCY, len(unique_urls))
        ) as executor:
            soups = executor.map(self.fetch_news_with_fallback, unique_urls)
            return dict(zip(unique_urls, soups))

    def fetch_news_with_proxy(self, target_url: str):
        proxy_url = PROXY 

        proxy_configuration = {
            "http": proxy_url,
            "https": proxy_url
        }
        
        if 'edgeprop' in target_url:
            headers = {
                "User-Agent": CRAWLER_USER_AGENT
            }
        
        else:
            headers = {
                "User-Agent": USER_AGENT
            }

        response = None

        try:
            LOGGER.info("Routing %s through proxy", target_url)
            response = requests.get(
                target_url, 
                proxies=proxy_configuration, 
                headers=headers, 
                verify=False, 
                timeout=60 
            )
            
            if response.status_code != 200:
                LOGGER.info(
                    "[FAIL] Web Unlocker returned status code: %s",
                    response.status_code,
                )
                self.record_request_failure(
                    url=target_url,
                    reason="HTTPStatusError",
                    status_code=response.status_code,
                    message=f"Received status code {response.status_code}",
                )
                return ""

            self.record_request_success(
                status_code=response.status_code,
            )
            
            return response.text
        
        except Exception as network_error:
            LOGGER.error(
                "[FAIL] Request through Web Unlocker failed: %s",
                network_error,
            )
            self.record_request_failure(
                url=target_url,
                reason=type(network_error).__name__,
                status_code=(
                    response.status_code
                    if response is not None
                    else None
                ),
                message=str(network_error),
            )
            return ""

    # Will be overridden by subclass
    def extract_news(self):
        pass

    def extract_news_pages(self, num_pages, date):
        pass

    # Writer methods
    def write_json(self, jsontext, filename):
        json_path = Path("data") / f"{filename}.json"
        write_json_file(json_path, jsontext, indent=4)

    def write_file_soup(self, filetext, filename):
        with open(f'./data/{filename}.txt', 'w', encoding='utf-8') as f:
            f.write(filetext.prettify())

    def write_csv(self, data, filename):
        csv_path = Path("data") / f"{filename}.csv"
        write_csv_file(csv_path, data)
