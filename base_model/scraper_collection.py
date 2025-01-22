import requests
from bs4 import BeautifulSoup
import json
import csv
import ssl
import urllib.request
from scraper import Scraper
import os
from dotenv import load_dotenv

# Determine the base directory where the .env file is located
base_dir = os.path.dirname(os.path.abspath(__file__))  # This will resolve to the directory containing scraper.py
project_root = os.path.abspath(os.path.join(base_dir, '..'))  # Move one level up to the base folder

# Load the .env file from the base directory
load_dotenv(os.path.join(project_root, '.env'))

class ScraperCollection:
  scrapers: list[Scraper]