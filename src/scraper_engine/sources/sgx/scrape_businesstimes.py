from bs4 import BeautifulSoup
from datetime import datetime, timezone, timedelta

import requests
import json 
import time 
import logging 


LOGGER = logging.getLogger(__name__)


def format_iso_date(iso_str: str) -> str:
    if not iso_str: 
        return ""

    try:
        sgt = timezone(timedelta(hours=8))
        dt = datetime.fromisoformat(iso_str.replace('Z', '+00:00'))
        dt = dt.astimezone(sgt)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    
    except ValueError:
        return iso_str
    

def scrape_businesstimes(num_page: int):
    base_url = f'https://www.businesstimes.com.sg/keywords/sgx?page={num_page}'

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    all_news = []

    for page_num in range(1, num_page + 1):
        LOGGER.info(f"Scraping page straitsnews: {page_num}")

        params = {'page': page_num}

        try:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
            }
            response = requests.get(base_url, params=params, headers=headers)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')

            script_tag = soup.find('script', string=lambda tag: tag and 'window.__staticRouterHydrationData' in tag)
            
            if not script_tag:
                LOGGER.info(f"Could not find data script on page {page_num}")
                continue

            script_content = script_tag.string.strip()
            
            start_marker = 'JSON.parse("'
            end_marker = '");'
            
            start_index = script_content.find(start_marker)
            end_index = script_content.rfind(end_marker)

            if start_index == -1 or end_index == -1:
                LOGGER.info(f"Could not parse script markers on page {page_num}")
                continue

            start_index += len(start_marker)
            
            raw_escaped_str = script_content[start_index:end_index]
            
            try:
                json_str = json.loads(f'"{raw_escaped_str}"')
            except json.JSONDecodeError:
                # simple string replacement if the above fails
                json_str = raw_escaped_str.replace('\\"', '"').replace('\\\\', '\\')

            data = json.loads(json_str)
            
            loader_data = data.get("loaderData", {})

            # need to find dynamically the target/route key contains the cards 
            target_key = None 
            for key, value in loader_data.items():
                if value and isinstance(value, dict) and 'context' in value: 
                    payload = value.get('context', {}).get('payload', {})
                    if 'data' in payload and 'overview' in payload['data']:
                        target_key = key
                        articles = payload['data']['overview']
                        LOGGER.info(f"Found BT structure in key: {key}")
                        break
            
            if not target_key:
                LOGGER.info(f"Could not find payload/cards in JSON structure on page {page_num}")
                continue
            
            for article in articles:
                title = article.get('title', '')
                source = article.get('link', '')
                timestamp = article.get('updatedTime', '')

                all_news.append({
                    'title': title, 
                    'source': source, 
                    'timestamp': format_iso_date(timestamp)
                })
            
            time.sleep(2)
            
            return all_news
        
        except Exception as error:
            LOGGER.error(f'scrape_straitsnews_sgx error: {error}', exc_info=True) 
            return []


if __name__ == '__main__': 
    result = scrape_businesstimes(1)
    print(result)
