from datetime import datetime, timezone 
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup 

from scraper_engine.base.scraper import SeleniumScraper

import argparse 
import logging 
import time 


LOGGER = logging.getLogger(__name__)


class EdgeProp(SeleniumScraper):
    BASE_URL = "https://www.edgeprop.sg"

    def fetch_article_list(self, url: str) -> list:
        if not self.driver:
            return []

        intercept_script = """
            window.__intercepted_responses = [];
            const originalFetch = window.fetch;
            window.fetch = function(...args) {
                return originalFetch.apply(this, args).then(response => {
                    const cloned = response.clone();
                    if (typeof args[0] === 'string' && args[0].includes('/proxy/news')) {
                        cloned.json().then(data => {
                            window.__intercepted_responses.push(data);
                        });
                    }
                    return response;
                });
            };
        """

        self.driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": intercept_script
        })

        self.driver.get(url)
        time.sleep(5)

        api_data = self.driver.execute_script("return window.__intercepted_responses;")

        if api_data:
            return api_data[0].get("response", {}).get('results')

        LOGGER.warning("[EdgeProp SG] XHR interception failed, falling back to HTML parsing")
        soup = BeautifulSoup(self.driver.page_source, "html.parser")

        return soup.select("div.main-container")

    def parse_timestamp(self, raw_timestamp: str) -> str:
        if not raw_timestamp:
            return None

        try:
            dt = datetime.fromisoformat(raw_timestamp)

            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)

            return dt.astimezone(ZoneInfo("Asia/Singapore"))

        except (ValueError, AttributeError) as error:
            LOGGER.error("[EdgeProp SG] Failed to parse timestamp '%s': %s", raw_timestamp, error)
            return None
        
    def fetch_article_content(self, article_url: str) -> tuple[datetime | None, str | None]:
        html = self.fetch_news_with_proxy(article_url)

        if not html:
            return None, None

        soup = BeautifulSoup(html, "html.parser")

        content_div = soup.select_one("#detail-content")

        for caption_block in content_div.select("div.caption-image"):
            caption_block.decompose()

        paragraphs = []

        for paragraph_div in content_div.select("div.truncated_textview_box"):
            text = paragraph_div.get_text(separator=" ", strip=True)

            if not text or text.lower().startswith("read also"):
                continue

            paragraphs.append(text)

        article_body = "\n\n".join(paragraphs) or None

        return article_body

    def parse_articles(self, article_items: list, target_date: str) -> tuple[list, bool]:
        parsed_articles = []
        reached_older_date = False

        target_datetime = datetime(
            int(target_date[:4]),
            int(target_date[4:6]),
            int(target_date[6:]),
            tzinfo=ZoneInfo("Asia/Singapore"),
        )

        for article_item in article_items:
            title = article_item.get('title')
            relative_url = article_item.get('path')
            source_url = f"{self.BASE_URL}{relative_url}" 
 
            if not source_url:
                continue
 
            thumbnail_url = article_item.get('thumbnail')
            
            raw_time = article_item.get('created')
            published_at = datetime.fromtimestamp(int(raw_time), tz=ZoneInfo("Asia/Singapore"))

            article_body = self.fetch_article_content(source_url)
            time.sleep(0.3)
 
            if not published_at:
                LOGGER.info("[EdgeProp SG] Failed to parse timestamp for %s. Skipping.", source_url)
                continue
           
            if published_at < target_datetime:
                reached_older_date = True
                break
            
            parsed_articles.append({
                "title": title,
                "source": source_url,
                "thumbnail": thumbnail_url,
                "timestamp": published_at.strftime("%Y-%m-%d %H:%M:%S"),
                "article": article_body
            })
 
        return parsed_articles, reached_older_date

    def extract_news_pages(self, num_pages: int, date: str) -> list:
        page_number = 1
 
        while True:
            section_url = f'/property-news-search?combine=&field_tags_tid=&page={page_number}&page_size=20&sort_by=posted_desc&category='
            page_url = f"{self.BASE_URL}{section_url}"
 
            article_items = self.fetch_article_list(page_url)
 
            if not article_items:
                LOGGER.info("[EdgeProp SG] No articles found on page %d, stopping.", page_number)
                break
 
            articles, reached_older_date = self.parse_articles(article_items, date)
 
            self.articles.extend(articles)
            LOGGER.info("[EdgeProp SG] Page %d: %d articles collected.", page_number, len(articles))
 
            if reached_older_date:
                LOGGER.info("[EdgeProp SG] Reached articles older than %s, stopping.", date)
                break
 
            if num_pages is not None and page_number >= num_pages:
                break
 
            page_number += 1
            time.sleep(1)
 
        LOGGER.info("[EdgeProp SG] Total scraped: %d", len(self.articles))
        return self.articles


def main():
    scraper = EdgeProp()

    parser = argparse.ArgumentParser(description="Script for scraping data from edgeprop")
    parser.add_argument("date", type=str)
    parser.add_argument("filename", type=str, nargs="?", default="edgeprop")
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
    uv run -m src.scraper_engine.sources.sgx.scrape_edgeprop <date> [filename] [--pages N] [--csv]

    Examples:
    uv run -m src.scraper_engine.sources.sgx.scrape_edgeprop 20260427
    uv run -m src.scraper_engine.sources.sgx.scrape_edgeprop 20260608 test_scrape_edgeprop
    uv run -m src.scraper_engine.sources.sgx.scrape_edgeprop 20260427 test_scrape_edgeprop --pages 3 --csv
    """
    main()
    
