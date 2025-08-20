from selenium                           import webdriver
from selenium.webdriver.chrome.service  import Service as ChromeService
from webdriver_manager.chrome           import ChromeDriverManager
from selenium.webdriver.chrome.options  import Options
from bs4                                import BeautifulSoup
from dotenv                             import load_dotenv

import json
import csv
import ssl
import urllib.request
import requests
import os
import time 


# Determine the base directory where the .env file is located
base_dir = os.path.dirname(os.path.abspath(__file__)) 
project_root = os.path.abspath(os.path.join(base_dir, '..')) 

# Load the .env file from the base directory
load_dotenv(os.path.join(project_root, '.env'))

ssl._create_default_https_context = ssl._create_unverified_context

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
      print(f"Error fetching the URL: {e}")
      return BeautifulSoup()
    
  # Fetch news using urllib.request with proxy
  def fetch_news_with_proxy(self, url):
    try:
      self.proxy = os.environ.get("proxy")
      # print("proxy", self.proxy)

      proxy_support = urllib.request.ProxyHandler({'http': self.proxy,'https': self.proxy})
      opener = urllib.request.build_opener(proxy_support)
      urllib.request.install_opener(opener)

      with urllib.request.urlopen(url) as response:
        data = response.read()
        data = data.decode('utf-8')

      self.soup = BeautifulSoup(data, 'html.parser')
      return self.soup
    except Exception as e:
      print(f"Error fetching the URL: {e}")
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
      print(f'Error fetching article IMA: {error}')
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
  _shared_driver = None 

  def __init__(self):
    super().__init__()
    self.driver = None

  @classmethod
  def get_shared_driver(cls, is_headless: bool = True):
    if cls._shared_driver is None:
      chrome_options = Options()
      if is_headless:
        chrome_options.add_argument("--headless") 
      chrome_options.add_argument("--no-sandbox")
      chrome_options.add_argument("--disable-dev-shm-usage")
      chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36")
      service = ChromeService(ChromeDriverManager().install())
      driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver 
  
  @property
  def driver(self):
    if self._driver is None:
      self._driver = self.get_shared_driver()
    return self._driver
  
  @driver.setter
  def driver(self, value):
    self._driver = value
  
  @classmethod
  def close_shared_driver(cls):
    if cls._shared_driver:
      print("Closing shared WebDriver...")
      cls._shared_driver.quit()
      cls._shared_driver = None

  def setup_driver(self, is_headless: bool = True):
    # This method is now just for compatibility
    return self.get_shared_driver(is_headless)
  
  def fetch_news_with_selenium(self, url: str):
    try:
      self.driver.get(url)
      time.sleep(4)
      html_content = self.driver.page_source
      self.soup = BeautifulSoup(html_content, 'html.parser')
      return self.soup
    
    except Exception as error:
      print(f'Failed fetch news with selenium: {error}')  
      return BeautifulSoup()

  def close_driver(self):
    pass 