from datetime import datetime

from scraper_engine.base.scraper import SeleniumScraper
from scraper_engine.sources.idx.utils.constant import INDONESIAN_MONTHS

import argparse
import time
import logging 


LOGGER = logging.getLogger(__name__)


class BisnisMarket(SeleniumScraper):
    def fetch_article_list(self, url):
        soup = self.fetch_news_with_selenium(url)
        
        if not soup:
            LOGGER.info("[Bisnis Market] [FAIL] Failed to fetch HTML or timed out for %s", url)
            return []
        
        article_container = soup.find("div", id="indeksListView")

        if not article_container:
            LOGGER.info("[Bisnis Market] [FAIL] Target container 'indeksListView' not found.")
            return []
        
        articles_items = article_container.find_all("div", class_="artItem")

        return articles_items

    def fetch_article_timestamp(self, article_url: str) -> str:
        soup = self.fetch_news(article_url)

        if not soup:
            return None

        date_tag = soup.select_one("div.detailsAttributeDates")

        if not date_tag:
            return None

        return self.parse_absolute_date(date_tag.get_text(strip=True))

    def parse_articles(self, article_items: list) -> list:
        parsed_articles = []

        for article_item in article_items:
            link_tag = article_item.find("a", class_="artLink")
            title_tag = article_item.find("h4", class_="artTitle")
            date_tag = article_item.find("div", class_="artDate")

            if not link_tag or not title_tag or not date_tag:
                continue

            source_url = link_tag.get("href")
            title = title_tag.get_text(strip=True)
            raw_date = date_tag.get_text(strip=True)

            thumbnail_tag = article_item.select_one("div.artImg img")
            thumbnail_url = thumbnail_tag["src"] if thumbnail_tag else None

            if "menit yang lalu" in raw_date or "jam yang lalu" in raw_date:
                published_at = self.fetch_article_timestamp(source_url)
                time.sleep(0.5)

            else:
                published_at = self.parse_absolute_date(raw_date)

            if not published_at:
                LOGGER.info("[Bisnis Market] Failed to parse date for url: %s. Skipping.", source_url)
                continue
            
            print(published_at)
            parsed_articles.append({
                "title": title,
                "source": source_url,
                "thumbnail": thumbnail_url,
                "timestamp": published_at,
            })

        return parsed_articles
    
    def parse_absolute_date(self, raw_date: str) -> str:
        if not raw_date:
            return None

        try:
            cleaned = raw_date.strip()

            if "," in cleaned:
                cleaned = cleaned.split(", ", 1)[-1]

            cleaned = cleaned.replace("WIB", "").strip()
            date_parts = cleaned.split("|")

            if len(date_parts) != 2:
                return None

            date_part = date_parts[0].strip()
            time_part = date_parts[1].strip()

            parts = date_part.split()
            day = int(parts[0])
            month = INDONESIAN_MONTHS.get(parts[1])
            year = int(parts[2])

            if not month:
                return None

            hour, minute = time_part.split(":")
            parsed_date = datetime(year, month, day, int(hour), int(minute))

            return parsed_date.strftime("%Y-%m-%d %H:%M:%S")

        except (ValueError, IndexError, AttributeError) as error:
            LOGGER.error("[Bisnis Market] Error parsing date '%s': %s", raw_date, error)
            return None

    def extract_news_pages(self, num_pages: int, date: str) -> list:
        base_url = 'https://www.bisnis.com/index?categoryId=194&type=indeks&'

        year = date[:4]
        month = date[4:6]
        day = date[6:]
        formatted_date = f"{year}-{month}-{day}"

        page_number = 1
        seen_urls = set()
        
        while True:
            params = f"date={formatted_date}&page={page_number}"
            page_url = base_url + params
            
            article_items = self.fetch_article_list(page_url)

            if not article_items:
                LOGGER.info("[Bisnis Market] No articles found on page %d, stopping.", page_number)
                break

            articles = self.parse_articles(article_items)

            new_articles = [
                article for article in articles 
                if article.get('source') not in seen_urls
            ]

            if not new_articles:
                LOGGER.info("[Bisnis Market] Page %d returned duplicate articles, stopping.", page_number)
                break

            for article in articles: 
                seen_urls.add(article.get('source'))

            self.articles.extend(new_articles)
            LOGGER.info("[Bisnis Market] Page %d: %d articles collected.", page_number, len(new_articles))

            if num_pages is not None and page_number >= num_pages:
                break

            page_number += 1
            time.sleep(1)

        LOGGER.info("[Bisnis Market] Total scraped: %d", len(self.articles))
        return self.articles
    

def main():
    scraper = BisnisMarket()

    parser = argparse.ArgumentParser(description="Script for scraping data from Bisnis Market")
    parser.add_argument("date", type=str)
    parser.add_argument("filename", type=str, nargs="?", default="bisnismarket")
    parser.add_argument("--pages", type=int, default=None, help="Number of pages to scrape (default: all)")
    parser.add_argument("--csv", action="store_true", help="Flag to indicate write to csv file")

    args = parser.parse_args()

    try:
        scraper.extract_news_pages(args.pages, args.date)
        scraper.write_json(scraper.articles, args.filename)

        if args.csv:
            scraper.write_csv(scraper.articles, args.filename)

    finally:
        SeleniumScraper.close_shared_driver()


if __name__ == "__main__":
    """
    How to run:
    uv run -m src.scraper_engine.sources.idx.scrape_bisnis_com <date> [filename] [--pages N] [--csv]

    Examples:
    uv run -m src.scraper_engine.sources.idx.scrape_bisnis_com 20260427
    uv run -m src.scraper_engine.sources.idx.scrape_bisnis_com 20260427 test_bisnis_market
    uv run -m src.scraper_engine.sources.idx.scrape_bisnis_com 20260427 test_bisnis_market --pages 3 --csv
    """
    main()
