import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.common.exceptions import WebDriverException
from datetime import datetime
from urllib.parse import urlparse

from scraper_engine.base.scraper import get_chrome_info
from scraper_engine.config.conf import PROXY

import json
import time
import random
import platform
import logging 
import shutil 
import os 
import zipfile
import tempfile


LOGGER = logging.getLogger(__name__)


def create_proxy_extension(proxy_url: str) -> str:
    """
    Parses a proxy URL and generates an extension ZIP.
    """
    parsed = urlparse(proxy_url)
    
    # Extract components
    scheme = parsed.scheme or "http"
    host = parsed.hostname
    port = parsed.port
    user = parsed.username
    password = parsed.password

    manifest_json = """
    {
        "version": "1.0.0",
        "manifest_version": 2,
        "name": "Proxy Auth Extension",
        "permissions": [
            "proxy",
            "tabs",
            "unlimitedStorage",
            "storage",
            "<all_urls>",
            "webRequest",
            "webRequestBlocking"
        ],
        "background": {
            "scripts": ["background.js"]
        },
        "minimum_chrome_version": "22.0.0"
    }
    """

    background_js = f"""
    var proxy_config = {{
        mode: "fixed_servers",
        rules: {{
            singleProxy: {{
                scheme: "{scheme}",
                host: "{host}",
                port: parseInt({port})
            }},
            bypassList: ["localhost"]
        }}
    }};

    chrome.proxy.settings.set({{value: proxy_config, scope: "regular"}}, function() {{}});

    function handle_auth(details) {{
        return {{
            authCredentials: {{
                username: "{user}",
                password: "{password}"
            }}
        }};
    }}

    chrome.webRequest.onAuthRequired.addListener(
        handle_auth,
        {{urls: ["<all_urls>"]}},
        ['blocking']
    );
    """

    extension_path = os.path.join(tempfile.gettempdir(), f"proxy_auth_{host}_{port}.zip")
    with zipfile.ZipFile(extension_path, 'w') as extension_zip:
        extension_zip.writestr("manifest.json", manifest_json)
        extension_zip.writestr("background.js", background_js)

    return extension_path


def navigate_with_retry(driver, url: str, max_retries: int = 3) -> bool:
    """
    Tries to navigate to a URL. If the WAF resets the connection, 
    waits and retries.
    """
    for attempt in range(max_retries):
        try:
            LOGGER.info(f"Navigating to {url} (Attempt {attempt + 1}/{max_retries})")
            driver.get(url)
            return True 
        
        except WebDriverException as error:
            if "ERR_CONNECTION_RESET" in str(error) or "ERR_CONNECTION_CLOSED" in str(error):
                LOGGER.warning(f"Connection reset by WAF. Sleeping 10s before retry")
                time.sleep(10) 
                continue
            else:
                raise error
            
    return False


def extract_json_objects(text: str, target_key: str = '"data":'):
    """
    Generator that finds ALL occurrences of `target_key` and extracts 
    the valid JSON structure (Object or Array) immediately following it.
    """
    start_search = 0

    while True:
        # Find the next occurrence of "data":
        start_idx = text.find(target_key, start_search)
        if start_idx == -1:
            break
            
        # Move past the marker
        structure_start = start_idx + len(target_key)
        
        # Find the first opening bracket [ or {
        open_idx = -1
        stack = []
        
        # Scan forward to find start of structure
        for i in range(structure_start, min(structure_start + 50, len(text))):
            char = text[i]
            if char in ['[', '{']:
                open_idx = i
                stack.append(char)
                break
        
        # If no bracket found near marker, skip this occurrence
        if open_idx == -1:
            start_search = structure_start
            continue

        # Count brackets to find the end
        for i in range(open_idx + 1, len(text)):
            char = text[i]
            
            if char == '[': stack.append('[')
            elif char == '{': stack.append('{')
            elif char == ']':
                if stack and stack[-1] == '[': stack.pop()
            elif char == '}':
                if stack and stack[-1] == '{': stack.pop()
            
            if not stack:
                # Found the closing bracket
                json_str = text[open_idx : i+1]
                yield json_str
                # Continue searching after this object
                start_search = i + 1
                break
        else:
            # If loop finishes without empty stack, structure is malformed/incomplete
            start_search = structure_start


def format_iso_date(iso_str: str) -> str:
    if not iso_str: return ""
    try:
        dt = datetime.fromisoformat(iso_str.replace('Z', '+00:00'))
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    
    except ValueError:
        return iso_str


def scrape_bca(page_num: int) -> list[dict[str, any]]:
    LOGGER.info(f"Initializing BCA Scraper for page {page_num}...")

    options = uc.ChromeOptions()
    options.add_argument('--headless=new') 
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')

    options.add_argument('--window-size=1920,1080')
    
    # Force a standard User-Agent
    options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
    
    # Explicitly disable automation flags 
    options.add_argument('--disable-blink-features=AutomationControlled')
    
    # Ignore SSL errors (Cause sometimes WAFs reset connections on SSL handshake)
    options.add_argument('--ignore-certificate-errors')
    options.add_argument('--allow-running-insecure-content')

    if PROXY:
        parsed_proxy = urlparse(PROXY)
        if parsed_proxy.username and parsed_proxy.password:
            # Proxies with Auth
            extension_path = create_proxy_extension(PROXY)
            options.add_extension(extension_path)
        else:
            # Proxies without Auth 
            options.add_argument(f"--proxy-server={PROXY}")

    chrome_version, chrome_path = get_chrome_info()
    driver_path = shutil.which("chromedriver")

    try:
        driver = uc.Chrome(
            options=options, 
            use_subprocess=True, 
            version_main=chrome_version,
            browser_executable_path=chrome_path,
            driver_executable_path=driver_path if platform.system() == "Linux" else None
        )

    except Exception as error:
        LOGGER.error(f"Failed to initialize driver: {error}")
        return []

    results = []

    try:
        LOGGER.info("Priming session")

        if not navigate_with_retry(driver, "https://bcasekuritas.co.id/"):
            LOGGER.error("Failed to load homepage after retries. Aborting.")
            return []
        
        time.sleep(random.uniform(3, 5))

        target_url = f"https://bcasekuritas.co.id/en/latest-news/news?page={page_num}"
        
        if not navigate_with_retry(driver, target_url):
            LOGGER.error("Failed to load news page after retries.")
            return []
        
        time.sleep(8) 

        LOGGER.info("Scanning for valid News Data List")
        
        scripts = driver.find_elements(By.TAG_NAME, "script")
        
        for script in scripts:
            content = script.get_attribute("innerHTML")
            if 'self.__next_f.push' in content and 'current_page' in content:
                
                clean_content = content.replace('\\"', '"').replace('\\\\', '\\')
                
                # Iterate through ALL "data": blocks in this script
                for json_str in extract_json_objects(clean_content, '"data":'):
                    try:
                        parsed_data = json.loads(json_str)
                        
                        # We only want the LIST, not the single object
                        if isinstance(parsed_data, list):
                            LOGGER.info(f"Found a LIST with {len(parsed_data)} items. Verifying content")
                            
                            # Verify it contains news items (check for 'slug' or 'title_id')
                            if len(parsed_data) > 0 and ('slug' in parsed_data[0] or 'title_id' in parsed_data[0]):
                                LOGGER.info("Target Data Found!")
                                
                                for item in parsed_data:
                                    slug = item.get("slug", "")
                                    title = item.get("title_en") or item.get("title_id")

                                    results.append({
                                        "title": title,
                                        "timestamp": format_iso_date(item.get("published_at")),
                                        "source": f"https://bcasekuritas.co.id/en/latest-news/news/{slug}",
                                    })
                                break 

                    except json.JSONDecodeError:
                        continue
                
                if results: 
                    break 

        # DOM Fallback 
        if not results:
            LOGGER.info("JSON extraction failed. Falling back to DOM.")
            cards = driver.find_elements(By.CSS_SELECTOR, "div.bg-card")
            
            for card in cards:
                try:
                    try:
                        link_el = card.find_element(By.XPATH, "./..")
                        if link_el.tag_name != "a": link_el = card.find_element(By.TAG_NAME, "a")
                        link = link_el.get_attribute("href")
                    except: link = driver.current_url

                    title = card.find_element(By.TAG_NAME, "h6").get_attribute("textContent").strip()
                    date_text = card.find_element(By.CSS_SELECTOR, "span.text-xs").get_attribute("textContent").strip()
                    if "|" in date_text: date_text = date_text.split("|")[-1].strip()
                    
                    try:
                        dt = datetime.strptime(date_text, "%d %b %Y")
                        date_formatted = dt.strftime("%Y-%m-%d 00:00:00")
                    except:
                        date_formatted = date_text

                    results.append({
                        "title": title,
                        "timestamp": date_formatted,
                        "source": link,
                    })
                except: continue

        # LOGGER.info(json.dumps(results, indent=2))
        LOGGER.info(f'Data parsed total: {len(results)}')
        return results

    except Exception as error:
        LOGGER.error(f"Fatal error: {error}")
        return []
    
    finally:
        try: driver.quit()
        except: pass


def run_scrape_bca_news(num_page: int) -> list[dict[str, any]]:
    all_articles = []

    for page in range(1, num_page + 1):
        article = scrape_bca(page)
        all_articles.extend(article)
        time.sleep(1.5)
    
    return all_articles


if __name__ == "__main__":
    scrape_bca(2)
