from datetime import datetime

from scraper_engine.base.scraper import SeleniumScraper

import argparse
import logging 
import time 


LOGGER = logging.getLogger(__name__)


class JakartaGlobe(SeleniumScraper):
    def fetch_article_list(self, url: str) -> list:
        soup = self.fetch_news_with_selenium(url)

        if not soup:
            LOGGER.info("[Jakarta Globe] [FAIL] Failed to fetch HTML or timed out for %s", url)
            return []

        return soup.find_all("div", class_="row mb-4 position-relative")

    def fetch_article_timestamp(self, article_url: str) -> str:
        soup = self.fetch_news_with_selenium(article_url)

        if not soup:
            return None

        date_span = soup.select_one("div.col.small.pt-1 span.text-muted")

        if not date_span:
            return None

        return self.parse_timestamp(date_span.get_text(strip=True))

    def parse_timestamp(self, raw_timestamp: str) -> str:
        if not raw_timestamp:
            return None

        try:
            cleaned = raw_timestamp.strip().replace("|", "").strip()
            parsed_date = datetime.strptime(cleaned, "%B %d, %Y %I:%M %p")
            return parsed_date.strftime("%Y-%m-%d %H:%M:%S")
        
        except ValueError as error:
            LOGGER.error("[Jakarta Globe] Error parsing date '%s': %s", raw_timestamp, error)
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
            anchor_tag = article_item.select_one("div.col-4 a")

            if not anchor_tag:
                continue

            relative_url = anchor_tag.get("href")
            source_url = f"https://jakartaglobe.id{relative_url}" if relative_url and relative_url.startswith("/") else relative_url

            if not source_url:
                continue

            title_tag = article_item.select_one("div.col-8.pt-l h4")
            title = title_tag.get_text(strip=True) if title_tag else None

            thumbnail_tag = article_item.select_one("div.col-4 img.lazy")
            thumbnail_url = thumbnail_tag.get("src") if thumbnail_tag else None

            published_at = self.fetch_article_timestamp(source_url)
            time.sleep(0.5)

            if not published_at:
                LOGGER.info("[Jakarta Globe] Failed to parse date for url: %s. Skipping.", source_url)
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
        # Jakarta Globe pagination is broken on the site, single page only
        page_url = "https://jakartaglobe.id/business/newsindex"

        article_items = self.fetch_article_list(page_url)
        
        if not article_items:
            LOGGER.info("[Jakarta Globe] No articles found, stopping.")
            return self.articles

        articles, reached_older_date = self.parse_articles(article_items, date)
        self.articles.extend(articles)

        if reached_older_date:
            LOGGER.info("[Jakarta Globe] Reached articles older than %s, stopping.", date)

        LOGGER.info("[Jakarta Globe] Total scraped: %d", len(self.articles))

        return self.articles


def main():
    scraper = JakartaGlobe()

    parser = argparse.ArgumentParser(description="Script for scraping data from Jakarta Globe")
    parser.add_argument("date", type=str)
    parser.add_argument("filename", type=str, nargs="?", default="jakartaglobe")
    parser.add_argument("--pages", type=int, default=None, help="Reserved for pipeline consistency, no effect")
    parser.add_argument("--csv", action="store_true", help="Flag to indicate write to csv file")

    args = parser.parse_args()

    scraper.extract_news_pages(args.pages, args.date)
    scraper.write_json(scraper.articles, args.filename)

    if args.csv:
        scraper.write_csv(scraper.articles, args.filename)


if __name__ == "__main__":
    '''
    How to run:
    uv run -m src.scraper_engine.sources.idx.scrape_jakartaglobe <date> [filename] [--pages N] [--csv]

    Examples:
    uv run -m src.scraper_engine.sources.idx.scrape_jakartaglobe 20260427
    uv run -m src.scraper_engine.sources.idx.scrape_jakartaglobe 20260427 test_jakartaglobe
    uv run -m src.scraper_engine.sources.idx.scrape_jakartaglobe 20260427 test_jakartaglobe --pages 3 --csv
    '''
    main()
