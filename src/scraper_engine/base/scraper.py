import undetected_chromedriver as uc
from bs4 import BeautifulSoup
from selenium.common.exceptions import TimeoutException

from scraper_engine.config.conf import PROXY, USER_AGENT

import json
import csv

import requests
import time
import logging 
import platform
import subprocess
import shutil


LOGGER = logging.getLogger(__name__)


def get_chrome_info() -> tuple:
    """
    Detects the installed Google Chrome version AND path.
    Returns a tuple: (major_version, executable_path)
    """
    operating_system = platform.system()
    if operating_system == "Linux":
        try:
            for binary in ["chrome", "google-chrome", "chromium", "chromium-browser"]:
                binary_path = shutil.which(binary)

                if not binary_path: 
                    continue
                
                try:
                    output = subprocess.check_output([binary_path, "--version"], text=True)
                    if not output: continue
                    
                    version_str = output.strip().split()[-1] 
                    major_version = int(version_str.split('.')[0])
                    
                    LOGGER.info(f"Detected {binary} at {binary_path} (Version: {major_version})")
                    return major_version, binary_path
                
                except:
                    continue
                
            return None, None
        
        except Exception as error:
            LOGGER.error(f"Could not detect Chrome version: {error}")
            return None, None
    
    elif operating_system == "Windows":
        try:
            command = 'powershell -command "(Get-ItemProperty -Path Registry::HKEY_CURRENT_USER\\Software\\Google\\Chrome\\BLBeacon).version"'
            output = subprocess.check_output(command, shell=True, text=True).strip()
            
            if output:
                major_version = int(output.split('.')[0])
                return major_version, None
            
        except subprocess.SubprocessError as process_error:
            LOGGER.error(f"Failed to query Windows registry: {process_error}")
            return None, None


class Scraper:
    soup: BeautifulSoup
    articles: list
    proxy: str | None

    def __init__(self):
        self.articles = []

    def fetch_news(self, url):
        try:
            response = requests.get(url)
            self.soup = BeautifulSoup(response.content, 'html.parser')
            return self.soup
        
        except Exception as e:
            LOGGER.error(f"Error fetching the URL: {e}")
            return BeautifulSoup()

    def fetch_news_with_proxy(self, target_url: str):
        proxy_url = PROXY 

        proxy_configuration = {
            "http": proxy_url,
            "https": proxy_url
        }
        
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

    def extract_news_pages(self, num_pages):
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

    def setup_driver(self, load_strategy: str = "normal", page_timeout: int = 120):
        """
        Initializes the Undetected Chrome Driver.
        Used for ALL scraping now.
        """
        LOGGER.info("Initializing Undetected Chrome Driver")
        options = uc.ChromeOptions()
        
        options.add_argument('--headless=new') 
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-gpu')
        
        options.add_argument('--window-size=1920,1080')
        options.add_argument(
            '--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        options.add_argument('--disable-blink-features=AutomationControlled')

        options.page_load_strategy = load_strategy

        chrome_version, chrome_path = get_chrome_info()
        driver_path = shutil.which("chromedriver")

        try:
            new_driver = uc.Chrome(
                options=options, 
                use_subprocess=True, 
                version_main=chrome_version,
                browser_executable_path=chrome_path, 
                driver_executable_path=driver_path if platform.system() == "Linux" else None
            )
            
            new_driver.set_page_load_timeout(page_timeout)

            SeleniumScraper._driver_instance = new_driver
            
        except Exception as error:
            LOGGER.error(f"Failed to initialize driver: {error}")
            SeleniumScraper._driver_instance = None

    def fetch_news_with_selenium(self, url: str):
        if not self.driver: 
            return BeautifulSoup()

        try:
            LOGGER.info(f"Navigating to {url}")
            self.driver.get(url)
            time.sleep(5) 

            html_content = self.driver.page_source
            self.soup = BeautifulSoup(html_content, 'html.parser')
            return self.soup
        
        except TimeoutException:
            LOGGER.warning(f"Page load timed out for {url}. Attempting to salvage available DOM.")
            try:
                html_content = self.driver.page_source
                self.soup = BeautifulSoup(html_content, 'html.parser')
                return self.soup
            except Exception as dom_error:
                LOGGER.error(f"Failed to extract DOM after timeout: {dom_error}")
                self.close_shared_driver()
                return None

        except Exception as error:
            LOGGER.error(f'Failed fetch news with selenium: {error}')  
            self.close_shared_driver()
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

