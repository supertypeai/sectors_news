import undetected_chromedriver as uc
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup
from selenium.common.exceptions import TimeoutException
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from scrapling import Fetcher

from scraper_engine.config.conf import PROXY, USER_AGENT, HEADERS_SCRAPER, CRAWLER_USER_AGENT

import json
import csv

import requests
import time
import logging 
import platform
import subprocess
import shutil
import os 
import re 


LOGGER = logging.getLogger(__name__)

UC_CACHE_PATH = os.path.expanduser("~/.local/share/undetected_chromedriver/undetected_chromedriver")


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
                        LOGGER.warning(f"Could not parse version from {binary_path} output: {output.strip()!r}")
                        continue

                    major_version = int(version_match.group(1))
                    LOGGER.info(f"Detected {binary} at {binary_path} (Version: {major_version})")
                    
                    return major_version, binary_path
                
                except (subprocess.SubprocessError, subprocess.TimeoutExpired, ValueError) as detection_error:
                    LOGGER.warning(f"Failed to detect version from {binary_path}: {detection_error}")
                    continue
            
            return None, None
        
        except Exception as error:
            LOGGER.error(f"Could not detect Chrome version: {error}")
            return None, None

    elif operating_system == "Windows":
        try:
            command = (
                "powershell -command "
                '"(Get-ItemProperty -Path Registry::HKEY_CURRENT_USER\\Software\\Google\\Chrome\\BLBeacon).version"'
            )
            
            output = subprocess.check_output(command, shell=True, text=True).strip()
            
            if output:
                major_version = int(output.split(".")[0])
                return major_version, None
        
        except subprocess.SubprocessError as process_error:
            LOGGER.error(f"Failed to query Windows registry: {process_error}")
        
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
                    f"Cached chromedriver v{cached_major_version} != Chrome v{chrome_major_version}. "
                    f"Removing stale cache at {UC_CACHE_PATH}."
                )

                os.remove(UC_CACHE_PATH)

    except Exception as cache_error:
        LOGGER.warning(f"Could not verify cached chromedriver, removing to be safe: {cache_error}")
        
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
        retry = Retry(total=3, backoff_factor=2)
        adapter = HTTPAdapter(max_retries=retry)
        self.session.mount('http://', adapter)
        self.session.mount('https://', adapter)

    def fetch_news(self, url):
        try:
            response = self.session.get(url, headers=HEADERS_SCRAPER, timeout=10)
            self.soup = BeautifulSoup(response.content, 'html.parser')
            return self.soup

        except Exception as error:
            LOGGER.error(f"Error fetching the URL: {error}")
            return BeautifulSoup()

    def fetch_news_with_scrapling(self, url: str):
        response = Fetcher.get(
            url,
            stealthy_headers=True,
            impersonate="chrome",
        )

        if response.status != 200:
            LOGGER.warning("Non-200 status %d for %s", response.status, url)
            return None

        return BeautifulSoup(bytes(response.body), "html.parser")
    
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

        try:
            LOGGER.info(f"Routing {target_url} through proxy")
            response = requests.get(
                target_url, 
                proxies=proxy_configuration, 
                headers=headers, 
                verify=False, 
                timeout=60 
            )
            
            if response.status_code == 200:
                return response.text
                
            LOGGER.info(f"[FAIL] Web Unlocker returned status code: {response.status_code}")
            return ""
        
        except requests.exceptions.RequestException as network_error:
            LOGGER.error(f"[FAIL] Request through Web Unlocker failed: {network_error}")
            return ""

    def fetch_news_with_post(self, url: str, payload: dict):
        try:
            response = requests.post(url, data=payload)
            data = response.json()

            html_content = data.get('html_items')
            self.soup = BeautifulSoup(html_content, 'html.parser')
            return self.soup
        
        except Exception as error:
            LOGGER.error(f'Error fetching article IMA: {error}')
            return BeautifulSoup()

    # Will be overridden by subclass
    def extract_news(self):
        pass

    def extract_news_pages(self, num_pages, date):
        pass

    # Writer methods
    def write_json(self, jsontext, filename):
        with open(f'./data/{filename}.json', 'w') as f:
            json.dump(jsontext, f, indent=4)

    def write_file_soup(self, filetext, filename):
        with open(f'./data/{filename}.txt', 'w', encoding='utf-8') as f:
            f.write(filetext.prettify())

    def write_csv(self, data, filename):
        with open(f'./data/{filename}.csv', 'w', newline='', encoding='utf-8') as csv_file:

            csv_writer = csv.writer(csv_file)

            header = data[0].keys()
            csv_writer.writerow(header)

            for item in data:
                csv_writer.writerow(item.values())


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
                LOGGER.warning("Shared WebDriver session is dead. Rebuilding before use.")
                self.close_shared_driver()

            self.setup_driver()

        return SeleniumScraper._driver_instance

    def setup_driver(self, load_strategy: str = "normal", page_timeout: int = 120):
        LOGGER.info("Initializing Undetected Chrome Driver")

        chrome_version, chrome_path = get_chrome_info()

        if chrome_version is None:
            LOGGER.error("Chrome version detection failed entirely. Cannot initialize driver safely.")
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

            new_driver.set_page_load_timeout(page_timeout)
            SeleniumScraper._driver_instance = new_driver

            LOGGER.info(f"Driver initialized successfully with Chrome v{chrome_version}")
        
        except Exception as error:
            LOGGER.error(f"Failed to initialize driver: {error}")
            SeleniumScraper._driver_instance = None

    def fetch_news_with_selenium(
        self, 
        url: str, 
        wait_selector: str = None, 
        time_sleep: int = 5, 
        retry: bool = True
    ):
        driver = self.ensure_driver()

        if not driver:
            return BeautifulSoup()

        try:
            LOGGER.info(f"Navigating to {url}")
            driver.get(url)

            if wait_selector:
                WebDriverWait(driver, 30).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, wait_selector))
                )

            else:
                time.sleep(time_sleep)

            html_content = driver.page_source
            self.soup = BeautifulSoup(html_content, 'html.parser')

            return self.soup

        except TimeoutException:
            LOGGER.warning(f"Page load timed out for {url}. Attempting to salvage available DOM.")
            try:
                html_content = driver.page_source
                self.soup = BeautifulSoup(html_content, 'html.parser')
                return self.soup

            except Exception as dom_error:
                LOGGER.error(f"Failed to extract DOM after timeout: {dom_error}")
                self.close_shared_driver()
                return None

        except Exception as error:
            LOGGER.error(f'Failed fetch news with selenium: {error}')
            # The session is likely dead, tear it down so the next access rebuilds it.
            self.close_shared_driver()

            if retry:
                LOGGER.info(f"Rebuilding driver and retrying once for {url}")
                return self.fetch_news_with_selenium(url, wait_selector, time_sleep, _retry=False)

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

