import requests
from bs4 import BeautifulSoup
import json
import csv
import ssl
import urllib.request
import os
from dotenv import load_dotenv

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

      print("proxy", self.proxy)

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