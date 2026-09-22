from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup
from selenium.common.exceptions import TimeoutException

from scrapling.fetchers import FetcherSession

from pathlib import Path

from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from scraper_engine.config.conf import (
    PROXY, 
    USER_AGENT, 
    HEADERS_SCRAPER, 
    CRAWLER_USER_AGENT,
    BRIGHTDATA_API_KEY, 
    BRIGHTDATA_ZONE
)
from scraper_engine.utils.json_helpers import (
    write_csv as write_csv_file,
    write_json as write_json_file,
)

import undetected_chromedriver as uc
import requests
import time
import logging 
import platform
import subprocess
import shutil
import os 
import re 


LOGGER = logging.getLogger(__name__)

UC_CACHE_PATH = os.path.expanduser(
    "~/.local/share/undetected_chromedriver/undetected_chromedriver"
)


def get_chrome_info() -> tuple:
    operating_system = platform.system()

    if operating_system == "Linux":
        try:
            for binary in [
                "google-chrome", 
                "google-chrome-stable", 
                "chrome", 
                "chromium", 
                "chromium-browser"
            ]:
                binary_path = shutil.which(binary)
                
                if not binary_path:
                    continue

                try:
                    output = subprocess.check_output(
                        [binary_path, "--version"],
                        text=True,
                        stderr=subprocess.DEVNULL,
                        timeout=5,
                    )

                    version_match = re.search(r"(\d+)\.\d+\.\d+", output)

                    if not version_match:
                        LOGGER.warning(
                            "Could not parse version from %s output: %r",
                            binary_path,
                            output.strip(),
                        )
                        continue

                    major_version = int(version_match.group(1))
                    LOGGER.info(
                        "Detected %s at %s (Version: %s)",
                        binary,
                        binary_path,
                        major_version,
                    )
                    
                    return major_version, binary_path
                
                except (
                    subprocess.SubprocessError, 
                    subprocess.TimeoutExpired, 
                    ValueError
                ) as detection_error:
                    LOGGER.warning(
                        "Failed to detect version from %s: %s",
                        binary_path,
                        detection_error,
                    )
                    continue
            
            return None, None
        
        except Exception as error:
            LOGGER.error("Could not detect Chrome version: %s", error)
            return None, None

    elif operating_system == "Windows":
        try:
            command = (
                "powershell -command "
                '"(Get-ItemProperty -Path Registry::HKEY_CURRENT_USER\\Software\\Google\\Chrome\\BLBeacon).version"'
            )
            
            output = subprocess.check_output(
                command, 
                shell=True, 
                text=True
            ).strip()
            
            if output:
                major_version = int(output.split(".")[0])
                return major_version, None
        
        except subprocess.SubprocessError as process_error:
            LOGGER.error(
                "Failed to query Windows registry: %s",
                process_error,
            )
        
        return None, None


def clear_stale_chromedriver_cache(chrome_major_version: int) -> None:
    if not os.path.exists(UC_CACHE_PATH):
        return
    
    try:
        cached_output = subprocess.check_output(
            [UC_CACHE_PATH, "--version"],
            text=True,
            stderr=subprocess.DEVNULL,
            timeout=5,
        )

        version_match = re.search(r"(\d+)\.\d+\.\d+", cached_output)
        
        if version_match:
            cached_major_version = int(version_match.group(1))

            if cached_major_version != chrome_major_version:
                LOGGER.warning(
                    "Cached chromedriver v%s != Chrome v%s. "
                    "Removing stale cache at %s.",
                    cached_major_version,
                    chrome_major_version,
                    UC_CACHE_PATH,
                )

                os.remove(UC_CACHE_PATH)

    except Exception as cache_error:
        LOGGER.warning(
            "Could not verify cached chromedriver, removing to be safe: %s",
            cache_error,
        )
        
        try:
            os.remove(UC_CACHE_PATH)

        except OSError:
            pass


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
                LOGGER.warning(
                    "Non-200 status %d for %s",
                    response.status,
                    url,
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


class SeleniumScraper(Scraper):
    _driver_instance = None 

    def __init__(self):
        super().__init__()
    
    @property
    def driver(self):
        if SeleniumScraper._driver_instance is None:
            self.setup_driver()

        return SeleniumScraper._driver_instance

    @classmethod
    def _is_driver_alive(cls) -> bool:
        """
        Cheaply probe the shared session; a dead session raises here.
        """
        driver = cls._driver_instance

        if driver is None:
            return False

        try:
            # Lightweight command that fails fast if the session/process is gone.
            _ = driver.current_url
            return True

        except Exception:
            return False

    def ensure_driver(self):
        """
        Return a healthy shared driver, rebuilding it if the previous one died.

        This prevents one source's crash (which tears down the shared browser)
        from poisoning every Selenium source that runs after it.
        """
        if not SeleniumScraper._is_driver_alive():
            if SeleniumScraper._driver_instance is not None:
                LOGGER.warning(
                    "Shared WebDriver session is dead. Rebuilding before use."
                )
                self.close_shared_driver()

            self.setup_driver()

        return SeleniumScraper._driver_instance

    def setup_driver(
        self, 
        load_strategy: str = "normal", 
        page_timeout: int = 240
    ):
        LOGGER.info("Initializing Undetected Chrome Driver")

        chrome_version, chrome_path = get_chrome_info()

        if chrome_version is None:
            LOGGER.error(
                "Chrome version detection failed entirely. " \
                "Cannot initialize driver safely."
            )
            SeleniumScraper._driver_instance = None
            return

        clear_stale_chromedriver_cache(chrome_version)

        options = uc.ChromeOptions()
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-setuid-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_argument(
            "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.page_load_strategy = load_strategy

        try:
            new_driver = uc.Chrome(
                options=options,
                version_main=chrome_version,
                browser_executable_path=chrome_path,
            )

            new_driver.set_page_load_timeout(page_timeout + 30)
            SeleniumScraper._driver_instance = new_driver

            LOGGER.info(
                "Driver initialized successfully with Chrome v%s",
                chrome_version,
            )
        
        except Exception as error:
            LOGGER.error("Failed to initialize driver: %s", error)
            SeleniumScraper._driver_instance = None

    def fetch_news_with_selenium(
        self, 
        url: str, 
        wait_selector: str = None, 
        time_sleep: int = 5, 
        retry: bool = True
    ):
        driver = None

        try:
            driver = self.ensure_driver()

            if not driver:
                self.record_request_failure(
                    url=url,
                    reason="DriverUnavailable",
                    message="Selenium driver is not available",
                )
                return None

            LOGGER.info("Navigating to %s", url)
            driver.get(url)

            if wait_selector:
                WebDriverWait(driver, 30).until(
                    EC.presence_of_element_located(
                        (By.CSS_SELECTOR, wait_selector)
                    )
                )

            else:
                time.sleep(time_sleep)

            html_content = driver.page_source
            self.soup = BeautifulSoup(html_content, 'html.parser')

            self.record_request_success()

            return self.soup

        except TimeoutException:
            LOGGER.warning(
                "Page load timed out for %s. Attempting to salvage available DOM.",
                url,
            )
            try:
                html_content = driver.page_source
                self.soup = BeautifulSoup(html_content, 'html.parser')
                self.record_request_success()
                return self.soup

            except Exception as dom_error:
                LOGGER.error(
                    "Failed to extract DOM after timeout: %s",
                    dom_error,
                )

                self.record_request_failure(
                    url=url,
                    reason=type(dom_error).__name__,
                    message=str(dom_error),
                )
                self.close_shared_driver()

                return None

        except Exception as error:
            LOGGER.error("Failed fetch news with selenium: %s", error)
            # The session is likely dead, tear it down so the next access rebuilds it.
            self.close_shared_driver()

            if retry:
                LOGGER.info(
                    "Rebuilding driver and retrying once for %s",
                    url,
                )
                return self.fetch_news_with_selenium(
                    url, 
                    wait_selector, 
                    time_sleep, 
                    retry=False
                )

            self.record_request_failure(
                url=url,
                reason=type(error).__name__,
                message=str(error),
            )

            return None

    @classmethod
    def close_shared_driver(cls):
        if cls._driver_instance:
            LOGGER.info("Closing Shared WebDriver...")

            try: 
                cls._driver_instance.quit()

            except: 
                pass

            cls._driver_instance = None
