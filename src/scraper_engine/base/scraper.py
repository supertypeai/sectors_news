from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.options import Options
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from bs4 import BeautifulSoup

from scraper_engine.config.conf import PROXY

import json
import csv
import ssl
import urllib.request
import requests
import time
import logging 
import platform
import subprocess
import shutil


LOGGER = logging.getLogger(__name__)

ssl._create_default_https_context = ssl._create_unverified_context


def get_chrome_info() -> tuple:
    """
    Detects the installed Google Chrome version AND path.
    Returns a tuple: (major_version, executable_path)
    """
    if platform.system() == "Linux":
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
    
    # Windows fallback
    return 143, None


class Scraper:
    soup: BeautifulSoup
    articles: list
    proxy: str | None

    def __init__(self):
        self.articles = []

    # Fetch news using requests but no proxy
    def fetch_news(self, url):
        try:
            response = requests.get(url)
            self.soup = BeautifulSoup(response.content, 'html.parser')
            return self.soup
        
        except Exception as e:
            LOGGER.error(f"Error fetching the URL: {e}")
            return BeautifulSoup()

    # Fetch news using urllib.request with proxy
    def fetch_news_with_proxy(self, url):
        try:
            self.proxy = PROXY
            # print("proxy", self.proxy)

            proxy_support = urllib.request.ProxyHandler(
                {'http': self.proxy, 'https': self.proxy}
            )
            opener = urllib.request.build_opener(proxy_support)
            urllib.request.install_opener(opener)

            with urllib.request.urlopen(url) as response:
                data = response.read()
                data = data.decode('utf-8')

            self.soup = BeautifulSoup(data, 'html.parser')
            return self.soup

        except Exception as e:
            LOGGER.error(f"Error fetching the URL: {e}")
            return BeautifulSoup()

    # Fetch news using requests post
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

    def setup_driver(self):
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
        
        except Exception as error:
            LOGGER.error(f'Failed fetch news with selenium: {error}')  
            
            try:
                if SeleniumScraper._driver_instance:
                    SeleniumScraper._driver_instance.quit()
                    SeleniumScraper._driver_instance = None
            except:
                pass
            
            return BeautifulSoup()

    @classmethod
    def close_shared_driver(cls):
        if cls._driver_instance:
            LOGGER.info("Closing Shared WebDriver...")
            try: 
                cls._driver_instance.quit()
            except: 
                pass
            cls._driver_instance = None

