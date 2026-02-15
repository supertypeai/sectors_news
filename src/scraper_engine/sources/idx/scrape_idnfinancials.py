from datetime import datetime

from scraper_engine.base.scraper import SeleniumScraper

import logging 
import argparse


LOGGER = logging.getLogger(__name__)


class IDNFinancialScraper(SeleniumScraper):
    def extract_news(self, url):
        soup = self.fetch_news_with_selenium(url)
        
        if not soup:
            LOGGER.error(f"Failed to fetch {url}")
            return []

        articles = []
        
        news_container = soup.find('div', class_='side-news')

        if not news_container:
            LOGGER.warning("Could not find 'side-news' container. Layout might have changed or page is empty.")
            return []

        # Items are in <ul class="list"> -> <li class="item">
        items = news_container.find_all('li', class_='item')
        
        LOGGER.info(f"Found {len(items)} items on page.")

        for item in items:
            try:
                # Link & Title
                # <a class="item-a d-flex" href="...">
                link_tag = item.find('a', class_='item-a')

                if not link_tag: 
                    continue
                
                link = link_tag.get('href')
                
                # Title is inside <div class="title">
                title_div = item.find('div', class_='title')
                title = title_div.get_text(strip=True) if title_div else ""
                
                if not title or not link: 
                    continue

                # Timestamp
                # <div class="date" data-date=">2026-02-13T12:38:18+07:00">
                date_div = item.find('div', class_='date')
                timestamp = None
                
                if date_div and date_div.has_attr('data-date'):
                    # The data-date format in HTML is ">2026-02-13T12:38:18+07:00"
                    raw_date = date_div['data-date'].replace('>', '').strip()
                    
                    try:
                        dt_obj = datetime.fromisoformat(raw_date)
                        timestamp = dt_obj.strftime("%Y-%m-%d %H:%M:%S")

                    except ValueError:
                        timestamp = raw_date
                
                if not timestamp and date_div:
                    LOGGER.info('Timestamp and date_div not found, timestamp return None')
                    return None 
                
                self.articles.append({
                    'title': title,
                    'source': link,
                    'timestamp': timestamp
                })
                
            except Exception as error:
                LOGGER.error(f"Error parsing item: {error}")
                continue
        
        return self.articles

    def extract_news_pages(self, num_pages):
        for index in range(num_pages):
            self.extract_news(self.get_page(index))

        return self.articles

    def get_page(self, page_num):
        return f'https://www.idnfinancials.com/search?q=idx&per_page={page_num}'


def main():
    scraper = IDNFinancialScraper()

    parser = argparse.ArgumentParser(
        description="Script for scraping data from idnfinancials"
    )
    parser.add_argument("page_number", type=int, default=1)
    parser.add_argument("filename", type=str, default="idnarticles")
    parser.add_argument(
        "--csv",
        action='store_true',
        help="Flag to indicate write to csv file"
    )

    args = parser.parse_args()
    num_page = args.page_number

    scraper.extract_news_pages(num_page)

    scraper.write_json(scraper.articles, args.filename)

    if args.csv:
        scraper.write_csv(scraper.articles, args.filename)


if __name__ == "__main__":
    """
    How to run:
    uv run -m src.scraper_engine.sources.idx.scrape_idnfinancials <page_number> <filename_saved> <--csv (optional)>
    """
    main()
