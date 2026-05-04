from datetime import datetime

from scraper_engine.base.scraper import SeleniumScraper

import argparse
import time
import logging 


LOGGER = logging.getLogger(__name__)


class BloombergTechnoz(SeleniumScraper):
    def fetch_article_list(self, url: str) -> list:
        soup = self.fetch_news_with_selenium(url)

        if not soup:
            LOGGER.info("[Bloomberg Technoz] [FAIL] Failed to fetch HTML or timed out for %s", url)
            return []

        main_container = soup.find("div", class_="col8 homepage_left")

        if not main_container:
            LOGGER.info("[Bloomberg Technoz] [FAIL] Target container 'co18 homepage_left' not found.")
            return []

        article_list = main_container.find_all("div", class_="card-box")
        
        return article_list 
    
    def fetch_article_timestamp(self, article_url: str) -> str:
        soup = self.fetch_news_with_selenium(article_url)

        if not soup:
            return None

        date_container = soup.find("div", class_="text-sumber")

        if not date_container:
            return None

        date_tag = date_container.find("h5", class_="title fw4 cl-gray margin-bottom-no")

        if not date_tag:
            return None

        return self.parse_timestamp(date_tag.get_text(strip=True))

    def parse_timestamp(self, raw_timestamp: str) -> str:
        if not raw_timestamp:
            return None

        try:
            parsed_date = datetime.strptime(raw_timestamp.strip(), "%d %B %Y %H:%M")
            return parsed_date.strftime("%Y-%m-%d %H:%M:%S")
        
        except ValueError:
            return None

    def parse_articles(self, article_items: list) -> list:
        parsed_articles = []
        seen_urls = set()

        for article_item in article_items:
            anchor_tag = article_item.find("a")

            if not anchor_tag:
                continue

            source_url = anchor_tag.get("href")

            if not source_url or source_url in seen_urls:
                continue

            title_tag = article_item.find(["h2", "h5", "h6"], class_="title")
            title = title_tag.get_text(strip=True) if title_tag else None

            thumbnail_tag = article_item.select_one("div.img-card img")
            thumbnail_url = thumbnail_tag["src"] if thumbnail_tag else None

            meta_tag = article_item.find("h6", class_="title fw4 cl-blue")
            published_at = None

            if meta_tag:
                meta_text = meta_tag.get_text(strip=True)
                if "|" in meta_text:
                    relative_time = meta_text.split("|")[-1].strip()

                    if (
                        "menit yang lalu" in relative_time or 
                        "jam yang lalu" in relative_time or 
                        'hari yang lalu' in relative_time
                    ):
                        published_at = self.fetch_article_timestamp(source_url)
                        time.sleep(0.5)

            if not published_at:
                LOGGER.info("[Bloomberg Technoz] Failed to extract timestamp for url: %s. Skipping.", source_url)
                continue

            print(published_at)

            seen_urls.add(source_url)
            parsed_articles.append({
                "title": title,
                "source": source_url,
                "thumbnail": thumbnail_url,
                "timestamp": published_at,
            })

        return parsed_articles

    def extract_news_pages(self, num_pages: int, date: str) -> list:
        year = date[:4]
        month = date[4:6]
        day = date[6:]
        formatted_date = f"{year}-{month}-{day}"

        # bloomberg technoz has no pagination, single page per date (num_pages only for inference pipeline)
        page_url = f"https://www.bloombergtechnoz.com/indeks/market/{formatted_date}"

        article_items = self.fetch_article_list(page_url)

        if not article_items:
            LOGGER.info("[Bloomberg Technoz] No articles found, stopping.")
            return self.articles

        articles = self.parse_articles(article_items)
        LOGGER.info("[Bloomberg Technoz] Date %s: %d articles collected.", date, len(articles))
        print(len(articles))

        self.articles.extend(articles)
        LOGGER.info("[Bloomberg Technoz] Total scraped: %d", len(self.articles))

        return self.articles


def main():
    scraper = BloombergTechnoz()

    parser = argparse.ArgumentParser(description="Script for scraping data from Bloomberg Technoz")
    parser.add_argument("date", type=str)
    parser.add_argument("filename", type=str, nargs="?", default="bloombergtechnoz")
    parser.add_argument("--pages", type=int, default=None, help="Reserved for pipeline consistency, no effect")
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
    uv run -m src.scraper_engine.sources.idx.scrape_bloomberg_technoz <date> [filename] [--pages N] [--csv]

    Examples:
    uv run -m src.scraper_engine.sources.idx.scrape_bloomberg_technoz 20260427
    uv run -m src.scraper_engine.sources.idx.scrape_bloomberg_technoz 20260427 test_bloomberg_technoz
    uv run -m src.scraper_engine.sources.idx.scrape_bloomberg_technoz 20260427 test__bloomberg_technoz --pages 3 --csv
    """
    main()
