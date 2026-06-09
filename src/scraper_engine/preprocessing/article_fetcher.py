from bs4 import BeautifulSoup
from goose3 import Goose
from io import StringIO
from scrapling import Fetcher, DynamicFetcher

from scraper_engine.config.conf import PROXY, USER_AGENT
from scraper_engine.base.scraper import SeleniumScraper, Scraper

import requests
import re
import cloudscraper
import logging
import csv


LOGGER = logging.getLogger(__name__)


def fetch_article_with_proxy(target_url: str) -> str:
    proxy_configuration = {
        "http": PROXY,
        "https": PROXY
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
            LOGGER.info("[SUCCESS] Web Unlocker with proxy")
            return response.text
        
        elif response.status_code == 403:
            LOGGER.error(f"[FAIL] Web Unlocker was blocked (403)")
            return None
        
        else:
            LOGGER.error(f"[FAIL] Target returned status code: {response.status_code}")
            return None
            
    except requests.exceptions.RequestException as network_error:
        LOGGER.error(f"[FAIL] Request through Web Unlocker failed: {network_error}")
        return None


def get_article_bca_news(url: str) -> str:
    headers = {
        "User-Agent": USER_AGENT
    }
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        title_tag = soup.find('h1')
        title = title_tag.get_text(strip=True) if title_tag else None

        article_container = soup.select_one('div.prose')
        
        if not article_container:
            LOGGER.info(f"Could not find 'div.prose' in {url}")
            return ""

        paragraphs = article_container.find_all('p')
        
        text_parts = []
        for paragraph in paragraphs:
            text = paragraph.get_text(strip=True)

            # Basic noise filter
            if text and text != "@": 
                text_parts.append(text)
                
        body = "\n\n".join(text_parts)
        body = body.replace('IQPlus,', '')

        article = f'{title}\n' + body
        return article 
    
    except Exception as error:
        LOGGER.error(f"[ERROR] Failed to extract {url}: {error}")
        return ""


def get_article_bloomberg_technoz_news(url: str) -> str:
    extracted_text_blocks = []
    
    request_headers = {
        "User-Agent": USER_AGENT
    }

    while url:
        try:
            response = requests.get(url, headers=request_headers, timeout=15)
            if response.status_code != 200:
                LOGGER.info(f"[FAIL] Server returned status code: {response.status_code} for URL: {url}")
                break
                
            soup = BeautifulSoup(response.text, "html.parser")
            article_container = soup.find("div", class_="detail-in")
            
            if article_container:
                paragraphs = article_container.find_all("p")
                
                for paragraph in paragraphs:
                    paragraph_text = paragraph.get_text(strip=True)
                    if paragraph_text:
                        extracted_text_blocks.append(paragraph_text)
            else:
                LOGGER.info(f"[FAIL] Could not find the 'detail-in' container on URL: {url}")
                
            # pagination logic: check if a next page exists
            pager_container = soup.find("div", class_="pager")
            if pager_container:
                next_page_element = pager_container.find("a", class_="pager__next")

                if next_page_element and next_page_element.get("href"):
                    url = next_page_element.get("href")
                    continue
                    
            url = None
                
        except requests.RequestException as network_error:
            LOGGER.error(f"[FAIL] Network error occurred: {network_error}")
            break
            
    full_article_text = "\n\n".join(extracted_text_blocks)
    return full_article_text


def get_article_investorid_news(url: str) -> str:
    html_content = fetch_article_with_proxy(url)

    if not html_content:
        LOGGER.info(f"[FAIL INVESTOR.ID] Proxy failed to retrieve HTML for {url}")
        return ""

    soup = BeautifulSoup(html_content, "html.parser")
    
    article_container = soup.select_one("div.body-content")
    
    if not article_container:
        return ""

    paragraphs = article_container.find_all("p")
    extracted_text_blocks = []
    
    for paragraph in paragraphs:
        paragraph_text = paragraph.get_text(strip=True)
        if paragraph_text:
            extracted_text_blocks.append(paragraph_text)
            
    full_article_text = "\n\n".join(extracted_text_blocks)
    return full_article_text


def get_article_kontan_news(url: str) -> str: 
    html_content = fetch_article_with_proxy(url)
    
    if not html_content:
        LOGGER.warning(f"[FAIL INVESTASI KONTAN] Proxy failed to retrieve HTML for {url}")
        return ""
        
    soup = BeautifulSoup(html_content, "html.parser")

    article_container = soup.find('div', class_='tmpt-desk-kon')
    
    if not article_container:
        LOGGER.warning(f"[FAIL] Could not find 'tmpt-desk-kon' container for {url}")
        return ""

    for strong_tag in article_container.find_all('strong'):
        if 'Baca Juga:' in strong_tag.get_text(strip=True):
            parent_paragraph = strong_tag.find_parent('p')

            if parent_paragraph:
                parent_paragraph.decompose()

    paragraphs = article_container.find_all('p')
    extracted_text_blocks = []
    
    for paragraph in paragraphs:
        paragraph_text = paragraph.get_text(strip=True)
      
        if paragraph_text:
            extracted_text_blocks.append(paragraph_text)
            
    full_article_text = "\n\n".join(extracted_text_blocks)
    
    related_news_pattern = r'(?i)berita\s+terkait.*'
    cleaned_article_text = re.sub(related_news_pattern, '', full_article_text, flags=re.DOTALL)
    
    return cleaned_article_text.strip()


def get_article_edgeprop_news(url: str) -> str | None:
    scraper = Scraper()
    soup = scraper.fetch_news(url)

    content_div = soup.select_one("#detail-content")

    if not content_div:
        LOGGER.warning(
            "[Fail Edgeprop] detail-content container not found for %s", url
        )
        return None

    # caption-image is always the parent of caption truncated_textview_box nodes.
    # Decompose them first so they are excluded from the text collection below.
    for caption_block in content_div.select("div.caption-image"):
        caption_block.decompose()

    paragraphs = []
    for paragraph_div in content_div.select("div.truncated_textview_box"):
        text = paragraph_div.get_text(separator=" ", strip=True)

        if not text:
            continue

        if text.lower().startswith("read also"):
            continue

        paragraphs.append(text)

    if not paragraphs:
        LOGGER.warning(
            "[Fail Edgeprop] No article text found for %s", url
        )
        return None

    return "\n\n".join(paragraphs)


def extract_table_content(url: str) -> str:
    headers = {
        "User-Agent": USER_AGENT
    }
    res = requests.get(url, headers=headers)
    res.raise_for_status()

    soup = BeautifulSoup(res.text, "html.parser")
     
    content_buffer = []
    
    # Find all Datawrapper iframes
    iframes = soup.find_all('iframe', src=lambda x: x and 'datawrapper.dwcdn.net' in x)
    
    for iframe in iframes:
        src = iframe['src']
      
        if src.startswith('//'):
            src = 'https:' + src
            
        try:
            # Datawrapper often exposes data at /dataset.csv
            # Example: https://datawrapper.dwcdn.net/ZslC8/3/ -> https://datawrapper.dwcdn.net/ZslC8/3/dataset.csv
            if src.endswith('/'):
                csv_url = src + 'dataset.csv'
            else:
                csv_url = src + '/dataset.csv'
                
            response = requests.get(csv_url, timeout=5)
            
            if response.status_code == 200:
                csv_text = response.text
                reader = csv.reader(StringIO(csv_text))
                
                # Format as plain text for llm input
                formatted_table = "\nDetail each company in a table form:\n"
                for row in reader:
                    formatted_table += " | ".join(row) + "\n"
                
                content_buffer.append(formatted_table)
                continue 
                
        except Exception:
            pass
            
        # If CSV fails, fetch the iframe HTML and get the title/aria-label
        # (Fallback for when dataset.csv is disabled)
        try:
            response = requests.get(src, timeout=5)
            if response.status_code == 200:
                iframe_soup = BeautifulSoup(response.text, 'html.parser')
                
                # Datawrapper usually puts the title in the <title> tag
                title = iframe_soup.title.string if iframe_soup.title else ""
                content_buffer.append(f"\n[Chart/Table: {title}] (Data extraction failed, view at {src})\n")
                
        except Exception as error:
            LOGGER.info(f"Failed to expand Datawrapper: {error}")
            return ''

    return "\n".join(content_buffer)


def extract_via_custom_parser(url: str) -> str | None: 
    try:
        LOGGER.info(f'Attempting custom parser')

        parser = {
            'bcasekuritas.co.id': get_article_bca_news, 
            'bloomberg': get_article_bloomberg_technoz_news, 
            # 'investor.id': get_article_investorid_news,
            'investasi.kontan': get_article_kontan_news,
            'edgeprop': get_article_edgeprop_news, 
        }

        for key, parser in parser.items(): 
            if key in url: 
                article = parser(url) 

                if not article: 
                    LOGGER.warning(f'[FAIL CUSTOM PARSER] Failed to extract {url}')
                    return None 
                
                LOGGER.info(f'[SUCCESS] Extracted via custom parser: {url}')
                return article

    except Exception as error:
        LOGGER.error(f"[FAIL] Custom parser failed: {error}")
        return None


def extract_via_scrapling(url: str) -> str | None:
    try:
        LOGGER.info("[TIER 1] Attempting extraction via Scrapling")
        response = Fetcher.get(url, stealthy_headers=True, impersonate="chrome")

        if response.status != 200:
            LOGGER.warning("[TIER 1] Non-200 status %d for %s", response.status, url)
            return None

        body = bytes(response.body)

        if b"Please wait while your request is being verified" in body:
            LOGGER.info("[TIER 1] Challenge page detected, falling back to DynamicFetcher")
            
            dynamic_response = DynamicFetcher.fetch(url, headless=True)
            body = bytes(dynamic_response.body)

        goose_extractor = Goose({"browser_user_agent": USER_AGENT})
        article_data = goose_extractor.extract(raw_html=body)

        return article_data.cleaned_text or None

    except Exception as error:
        LOGGER.error("[TIER 1] Scrapling extraction failed for %s: %s", url, error)
        return None


def extract_via_cloudscraper(url: str) -> str | None: 
    try:
        LOGGER.info(f"[TIER 2] Attempting fast extraction (No Proxy)")
        scraper_session = cloudscraper.create_scraper() 
        goose_extractor = Goose(
            {'browser_user_agent': USER_AGENT, 'http_session': scraper_session}
        )

        article_data = goose_extractor.extract(url=url)
        
        if article_data and article_data.cleaned_text:
            LOGGER.info(f"[SUCCESS] Extracted via Cloudscraper + Goose: {url}")
            extracted_text = article_data.cleaned_text
            
            if 'www.straitstimes' in url:
                extracted_text = extracted_text.replace("Sign up now: Get ST's newsletters delivered to your inbox", "")
                
            return extracted_text
            
    except Exception as error:
        LOGGER.error(f"[FAIL] Tier 2 Cloudscraper failed: {error}")
        return None 


def extract_via_selenium(url: str) -> str | None: 
    try:
        LOGGER.info(f"[TIER 2] Attempting Selenium extraction (No Proxy)")
        selenium_scraper = SeleniumScraper()
        soup_result = selenium_scraper.fetch_news_with_selenium(url)

        if soup_result:
            raw_html_content = str(soup_result)

            goose_extractor = Goose()
            article_data = goose_extractor.extract(raw_html=raw_html_content)
            
            if article_data and article_data.cleaned_text:
                LOGGER.info(f"[SUCCESS] Extracted via Selenium + Goose: {url}")
                return article_data.cleaned_text
                
            LOGGER.info("[WARNING] Selenium DOM fetched, but Goose failed. Attempting Soup fallbacks.")
            
            content_container = soup_result.find("div", class_="content")
            
            if content_container and content_container.get_text(strip=True):
                LOGGER.info(f"[SUCCESS] Extracted via Selenium + Soup: {url}")
                return content_container.get_text(strip=True)
            
            antara_container = soup_result.find("div", class_="wrap__article-detail")
            
            if antara_container and antara_container.get_text(strip=True):
                LOGGER.info(f"[SUCCESS] Extracted via Selenium + Soup: {url}")
                return antara_container.get_text(strip=True)

    except Exception as error:
        LOGGER.error(f"[FAIL] Tier 2 Selenium fallback failed: {error}")    
        return None 


def extract_via_proxy(url: str) -> str | None: 
    try:
        LOGGER.info(f"[TIER 3] Escalating to Proxy")
        
        raw_html_content = fetch_article_with_proxy(url)

        if not raw_html_content:
            LOGGER.warning(f"[FAIL] Proxy network request failed for {url}")
            return None
            
        goose_extractor = Goose()
        article_data = goose_extractor.extract(raw_html=raw_html_content)

        if article_data and article_data.cleaned_text:
            LOGGER.info(f"[SUCCESS] Extracted via Proxy + Goose: {url}")
            return article_data.cleaned_text

    except Exception as error:
        LOGGER.error(f"[FAIL] Tier 3 Proxy extraction failed: {error}")
        return None


def get_article_body(url: str) -> str | None:
    if extracted_text := extract_via_custom_parser(url):
        return extracted_text 

    if extracted_text := extract_via_scrapling(url):
        return extracted_text 
    
    if extracted_text := extract_via_cloudscraper(url):
        return extracted_text 
 
    if extracted_text := extract_via_selenium(url):
        return extracted_text 

    if extracted_text := extract_via_proxy(url):
        return extracted_text 

    LOGGER.info(f"[FATAL] All extraction tiers failed to retrieve body for: {url}")
    return None