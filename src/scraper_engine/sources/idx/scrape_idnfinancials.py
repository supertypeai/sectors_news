from datetime import datetime

from scraper_engine.base.scraper import SeleniumScraper

import logging 
import argparse
import re 


LOGGER = logging.getLogger(__name__)


class IDNFinancialScraper(SeleniumScraper):
    def fetch_article_list(self, url: str):
        soup = self.fetch_news_with_selenium(url)

        if not soup:
            LOGGER.error(f"Failed to fetch {url}")
            return []

        news_container = soup.find('div', class_='news')
        
        if not news_container:
            LOGGER.warning("Could not find 'news' container. Layout might have changed or page is empty.")
            return []

        featured_items = news_container.find_all('div', class_='first')
        grid_items = news_container.find_all('div', class_='ln-item')
        widget_items = news_container.find_all('article', class_='item')
        article_items = featured_items + grid_items + widget_items
        
        return article_items

    def parse_articles(self, article_items: list, target_date: str) -> tuple[list, bool]:
        parsed_articles = []
        reached_older_date = False

        target_datetime = datetime(
            int(target_date[:4]),
            int(target_date[4:6]),
            int(target_date[6:]),
        )

        for article_item in article_items:
            anchor_tag = article_item.find('a')
            
            if not anchor_tag:
                continue

            source_url = anchor_tag.get('href')

            title_tag = article_item.find(['h1', 'h2'], class_='title')
            title = title_tag.get_text(strip=True) if title_tag else None

            image_div = (
                article_item.find('div', class_='image')
                or article_item.find('div', class_='st-image')
            )
            
            
            thumbnail_url = None
            if image_div and image_div.get('style'):
                match = re.search(r'url\("(.+?)"\)', image_div['style'])
                
                if match:
                    thumbnail_url = match.group(1)

            date_tag = article_item.find('p', class_='date-published')
            
            published_at = None
            
            if date_tag and date_tag.get('data-date'):
                raw_date = date_tag['data-date'].strip()
                
                try:
                    parsed_datetime = datetime.fromisoformat(raw_date)
                    article_date = datetime(parsed_datetime.year, parsed_datetime.month, parsed_datetime.day)
                    
                    if article_date < target_datetime:
                        reached_older_date = True
                        break
                    
                    published_at = parsed_datetime.strftime('%Y-%m-%d %H:%M:%S')

                except ValueError:
                    published_at = None

            if not title or not source_url:
                continue

            parsed_articles.append({
                'title': title,
                'source': source_url,
                'thumbnail': thumbnail_url,
                'timestamp': published_at,
            })

        return parsed_articles, reached_older_date

    def extract_news_pages(self, num_pages: int, date: str):
        page_number = 1
        while True:
            page_url = f'https://www.idnfinancials.com/id/news/page/{page_number}'
            
            article_items = self.fetch_article_list(page_url)

            if not article_items:
                LOGGER.info('[IDN Financials] No articles found on page %d, stopping.', page_number)
                break

            articles, reached_older_date = self.parse_articles(article_items, date)
            self.articles.extend(articles)
            LOGGER.info('[IDN Financials] Page %d: %d articles collected.', page_number, len(articles))

            if reached_older_date:
                LOGGER.info('[IDN Financials] Reached articles older than %s, stopping.', date)
                break

            if num_pages is not None and page_number >= num_pages:
                break

            page_number += 1

        LOGGER.info('[IDN Financials] Total scraped: %d', len(self.articles))
        return self.articles
  
      
def main():
    scraper = IDNFinancialScraper()

    parser = argparse.ArgumentParser(description="Script for scraping data from IDN Financials")
    parser.add_argument("date", type=str)
    parser.add_argument("filename", type=str, nargs="?", default="idnfinancials")
    parser.add_argument("--pages", type=int, default=None, help="Number of pages to scrape (default: all)")
    parser.add_argument("--csv", action="store_true", help="Flag to indicate write to csv file")

    args = parser.parse_args()

    scraper.extract_news_pages(args.pages, args.date)
    scraper.write_json(scraper.articles, args.filename)

    if args.csv:
        scraper.write_csv(scraper.articles, args.filename)


if __name__ == "__main__":
    """
    How to run:
    uv run -m src.scraper_engine.sources.idx.scrape_idnfinancials <date> [filename] [--pages N] [--csv]

    Examples:
    uv run -m src.scraper_engine.sources.idx.scrape_idnfinancials 20260427
    uv run -m src.scraper_engine.sources.idx.scrape_idnfinancials 20260624 test_idnfinancials
    uv run -m src.scraper_engine.sources.idx.scrape_idnfinancials 20260427 test_idnfinancials --pages 3 --csv
    """
    main()
