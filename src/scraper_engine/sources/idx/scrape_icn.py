from datetime import datetime

from scraper_engine.base.scraper import SeleniumScraper

import argparse
import logging
import time
import dateparser


LOGGER = logging.getLogger(__name__)


class ICNScraper(SeleniumScraper):
    def fetch_article_list(self, url: str) -> list:
        soup = self.fetch_news_with_selenium(url)

        if not soup:
            return []
        
        return soup.find_all("article")

    def parse_articles(self, article_items: list, target_date: str) -> tuple[list, bool]:
        parsed_articles = []
        reached_older_date = False

        target_datetime = datetime(
            int(target_date[:4]),
            int(target_date[4:6]),
            int(target_date[6:])
        )

        for article_item in article_items:
            card_div = article_item.find("div", class_="elementor-post__card")

            if not card_div:
                continue

            text_div = card_div.find("div", class_="elementor-post__text")

            if not text_div:
                continue

            title_heading = text_div.find("h3", class_="elementor-post__title")
            title_anchor = title_heading.find("a") if title_heading else None
            title = title_anchor.get_text(strip=True) if title_anchor else None

            source_anchor = card_div.find("a", class_="elementor-post__thumbnail__link")
            source = source_anchor["href"].strip() if source_anchor else None

            if not source:
                continue
            
            thumbnail_div = card_div.find("div", class_="elementor-post__thumbnail")
            thumbnail_img = thumbnail_div.find("img") if thumbnail_div else None
            thumbnail_url = thumbnail_img.get("src") if thumbnail_img else None

            meta_div = card_div.find("div", class_="elementor-post__meta-data")
            date_span = meta_div.find("span", class_="elementor-post-date") if meta_div else None
            raw_timestamp = date_span.get_text(strip=True) if date_span else None

            if not raw_timestamp:
                LOGGER.info("[ICN] Missing timestamp for %s. Skipping.", source)
                continue

            published_at = dateparser.parse(raw_timestamp)

            if not published_at:
                LOGGER.info("[ICN] Failed to parse timestamp '%s' for %s. Skipping.", raw_timestamp, source)
                continue

            if published_at < target_datetime:
                reached_older_date = True
                break

            parsed_articles.append({
                "title": title,
                "source": source,
                "thumbnail": thumbnail_url,
                "timestamp": published_at.strftime("%Y-%m-%d %H:%M:%S"),
            })

        return parsed_articles, reached_older_date

    def extract_news_pages(self, num_pages: int, date: str) -> list:
        base_url = 'https://www.indonesiancoalandnickel.com/lintasan-berita/page/'
        page_number = 1

        while True:
            page_url = f'{base_url}{page_number}/' 

            article_items = self.fetch_article_list(page_url)
            
            if not article_items:
                LOGGER.info("[ICN] No articles found on page %d, stopping.", page_number)
                break

            articles, reached_older_date = self.parse_articles(article_items, date)

            self.articles.extend(articles)
            LOGGER.info("[ICN] Page %d: %d articles collected.", page_number, len(articles))

            if reached_older_date:
                LOGGER.info("[ICN] Reached articles older than %s, stopping.", date)
                break

            if num_pages is not None and page_number >= num_pages:
                break

            page_number += 1
            time.sleep(1)

        LOGGER.info("[ICN] Total scraped: %d", len(self.articles))
        return self.articles

    def get_page(self, page_number: int) -> str:
        return f"https://www.indonesiancoalandnickel.com/lintasan-berita/page/{page_number}/"


def main():
    scraper = ICNScraper()

    parser = argparse.ArgumentParser(
        description="Script for scraping data from indonesiancoalandnickel"
    )
    parser.add_argument("date", type=str)
    parser.add_argument("filename", type=str, nargs="?", default="icnarticles")
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
    uv run -m scraper_engine.sources.idx.scrape_icn <date> [filename] [--pages N] [--csv]

    Examples:
    uv run -m scraper_engine.sources.idx.scrape_icn 20260521
    uv run -m scraper_engine.sources.idx.scrape_icn 20260521 test_icn
    uv run -m scraper_engine.sources.idx.scrape_icn 20260521 test_icn --pages 3 --csv
    """
    main()