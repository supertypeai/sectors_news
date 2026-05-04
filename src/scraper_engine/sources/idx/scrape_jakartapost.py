from datetime import datetime
from urllib.parse import urljoin

from scraper_engine.base.scraper import SeleniumScraper

import argparse
import time 
import re
import logging 


LOGGER = logging.getLogger(__name__)


class JakartaPost(SeleniumScraper):
    def fetch_article_list(self, url: str) -> list:
        soup = self.fetch_news_with_selenium(url)

        if not soup:
            LOGGER.info("[Jakarta Post] [FAIL] Failed to fetch HTML or timed out for %s", url)
            return []

        article_lists =  soup.select("div.listNews")

        return article_lists

    def fetch_article_timestamp(self, article_url: str) -> str:
        soup = self.fetch_news_with_selenium(article_url)

        if not soup:
            return None

        created_tags = soup.select("div.tjp-meta__content-item span.created")

        for created_tag in created_tags:
            raw_text = created_tag.get_text(strip=True)
            iso_match = re.search(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+\-]\d{2}:\d{2}", raw_text)

            if iso_match:
                try:
                    dt_obj = datetime.fromisoformat(iso_match.group())  
                    return dt_obj.strftime("%Y-%m-%d %H:%M:%S")
                
                except ValueError:
                    continue

        return None

    def parse_articles(self, article_items: list, target_date: str) -> tuple[list, bool]:
        parsed_articles = []
        reached_older_date = False

        target_datetime = datetime(
            int(target_date[:4]),
            int(target_date[4:6]),
            int(target_date[6:]),
        )

        for article_item in article_items:
            premium_badge = article_item.select_one("span.premiumBadge")

            if premium_badge:
                continue

            link_tag = article_item.select_one("a[href*='/business/']")
            title_tag = article_item.select_one("h2.titleNews")

            if not link_tag or not title_tag:
                continue

            title = title_tag.get_text(strip=True)
            relative_url = link_tag.get("href")
            relative_url = re.sub(r"\.html-\d+$", ".html", relative_url)
            source_url = urljoin("https://www.thejakartapost.com", relative_url)

            thumbnail_tag = article_item.select_one("img[data-src], img[src]")
            
            if not thumbnail_tag:
                continue 

            thumbnail_url = thumbnail_tag.get("data-src") or thumbnail_tag.get("src")
            
            published_at = self.fetch_article_timestamp(source_url)
            time.sleep(0.5)

            if not published_at:
                LOGGER.info("[Jakarta Post] Failed to parse date for url: %s. Skipping.", source_url)
                continue

            article_datetime = datetime.strptime(published_at[:10], "%Y-%m-%d")

            if article_datetime < target_datetime:
                reached_older_date = True
                break

            parsed_articles.append({
                "title": title,
                "source": source_url,
                "thumbnail": thumbnail_url,
                "timestamp": published_at,
            })

        return parsed_articles, reached_older_date

    def extract_news_pages(self, num_pages: int, date: str) -> list:
        base_url = "https://www.thejakartapost.com/business/markets"
        page_number = 1

        while True:
            page_url = f"{base_url}?page={page_number}"
            print(page_url)

            article_items = self.fetch_article_list(page_url)

            if not article_items:
                LOGGER.info("[Jakarta Post] No articles found on page %d, stopping.", page_number)
                break

            articles, reached_older_date = self.parse_articles(article_items, date)

            self.articles.extend(articles)
            LOGGER.info("[Jakarta Post] Page %d: %d articles collected.", page_number, len(articles))

            if reached_older_date:
                LOGGER.info("[Jakarta Post] Reached articles older than %s, stopping.", date)
                break

            if num_pages is not None and page_number >= num_pages:
                break

            page_number += 1
            time.sleep(1)

        LOGGER.info("[Jakarta Post] Total scraped: %d", len(self.articles))
        return self.articles


def main():
    scraper = JakartaPost()

    parser = argparse.ArgumentParser(description="Script for scraping data from The Jakarta Post")
    parser.add_argument("date", type=str)
    parser.add_argument("filename", type=str, nargs="?", default="jakartapost")
    parser.add_argument("--pages", type=int, default=None, help="Number of pages to scrape (default: all)")
    parser.add_argument("--csv", action="store_true", help="Flag to indicate write to csv file")

    args = parser.parse_args()

    scraper.extract_news_pages(args.pages, args.date)
    scraper.write_json(scraper.articles, args.filename)

    if args.csv:
        scraper.write_csv(scraper.articles, args.filename)


if __name__ == "__main__":
    '''
    How to run:
    uv run -m src.scraper_engine.sources.idx.scrape_jakartapost <date> [filename] [--pages N] [--csv]

    Examples:
    uv run -m src.scraper_engine.sources.idx.scrape_jakartapost 20260427
    uv run -m src.scraper_engine.sources.idx.scrape_jakartapost 20260427 test_jakarta_post
    uv run -m src.scraper_engine.sources.idx.scrape_jakartapost 20260427 test_jakarta_post --pages 3 --csv
    '''
    main()
