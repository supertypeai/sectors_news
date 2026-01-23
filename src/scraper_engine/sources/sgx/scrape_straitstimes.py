from datetime import datetime, timedelta, timezone

import requests
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
    

def scrape_straitsnews_sgx(pages_to_scrape=2):
    api_url = "https://www.straitstimes.com/_plat/api/v1/articlesListing"
    root_url = 'https://www.straitstimes.com'

    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }

    all_news = []

    for page_num in range(1, pages_to_scrape + 1):
        LOGGER.info(f"Scraping page straitsnews: {page_num}")
        
        params = {
            'pageType': 'tags',
            'searchParam': 'sgx',
            'page': page_num,
        }
        
        try:
            response = requests.get(api_url, params=params, headers=headers)
            response.raise_for_status()
            data = response.json()

            cards = data.get('cards', [])

            for card in cards: 
                article_card = card.get('articleCard')

                title = article_card.get('title', '')
                url = article_card.get('urlPath', '')
                timestamp = article_card.get('publishedDate', '')

                all_news.append({
                    'title': title, 
                    'source': f'{root_url}{url}', 
                    'timestamp': format_iso_date(timestamp)
                })
            
            time.sleep(2)

            return all_news

        except Exception as error:
            LOGGER.error(f'scrape_straitsnews_sgx error: {error}', exc_info=True) 
            return []


if __name__ == '__main__':
    scrape_straitsnews_sgx(1)
