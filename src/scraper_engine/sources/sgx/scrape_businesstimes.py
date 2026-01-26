from bs4 import BeautifulSoup
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.chrome.options import Options

import time 
import logging 


LOGGER = logging.getLogger(__name__)


def format_iso_date(iso_str: str) -> str:
    if not iso_str: 
        return ""

    try:
        dt = datetime.strptime(iso_str, "%b %d, %Y %I:%M %p")
        return dt.strftime("%Y-%m-%d %H:%M:%S")
            
    except ValueError:
        return iso_str
    

def scrape_businesstimes(num_page: int) -> list[dict[str]]:
    base_url = 'https://www.businesstimes.com.sg/keywords/sgx'
    
    chrome_options = Options()
    chrome_options.add_argument("--headless") 
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36")

    driver = webdriver.Chrome(options=chrome_options)
    all_news = []
    seen_urls = set()

    try:
        LOGGER.info(f"Opening Browser for {base_url}")
        driver.get(base_url)
        time.sleep(5)  

        # scroll 'num_page' times. Each scroll triggers a "Load More"
        for scroll_count in range(num_page):
            LOGGER.info(f"Scrolling batch {scroll_count + 1}/{num_page}")
            
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            
            # wait for the loading spinner / API fetch to finish
            time.sleep(4) 
            
            # optional: sometimes  need to scroll up slightly to trigger the event
            # driver.execute_script("window.scrollBy(0, -100);")

        LOGGER.info("Parsing fully loaded page content")
        soup = BeautifulSoup(driver.page_source, 'html.parser')

        cards = soup.find_all('div', attrs={'data-testid': 'basic-card-component'}) 

        for card in cards:
            title_tag = card.find('h3', attrs={'data-testid': 'card-title-component'})
            if not title_tag:
                continue

            link_tag = title_tag.find('a')
            if not link_tag:
                continue

            title = link_tag.get_text(strip=True)
            relative_url = link_tag.get('href', '')

            if relative_url.startswith('/'):
                url = f"https://www.businesstimes.com.sg{relative_url}"
            else:
                url = relative_url

            time_tag = card.find('div', attrs={'data-testid': 'created-time-component'})
            raw_time = time_tag.get_text(strip=True) if time_tag else ""
           
            if url and url not in seen_urls:
                seen_urls.add(url)
                all_news.append({
                    'title': title,
                    'source': url,
                    'timestamp': format_iso_date(raw_time) 
                })
        
        return all_news 
    
    except Exception as error:
        LOGGER.error(f'scrape_straitsnews_sgx error: {error}', exc_info=True) 
        return []  


if __name__ == '__main__': 
    result = scrape_businesstimes(1)
    print(result)
