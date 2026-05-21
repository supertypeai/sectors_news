import time
import argparse
import logging

from datetime import datetime
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup
import requests

from scraper_engine.base.scraper import SeleniumScraper


LOGGER = logging.getLogger(__name__)


class BusinessTimesSG(SeleniumScraper):
    def normalize_timestamp(self, raw_time_str: str) -> datetime | None:
        if not raw_time_str:
            return None

        try:
            dt = datetime.strptime(raw_time_str, "%b %d, %Y %I:%M %p")
            return dt.replace(tzinfo=ZoneInfo("Asia/Singapore"))

        except ValueError as error:
            LOGGER.error("[BT SG] Failed to parse timestamp '%s': %s", raw_time_str, error)
            return None

    def check_valid_article(self, url: str) -> bool:
        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, "html.parser")

            if soup.find(attrs={"data-testid": "kicker-subscriber-label-separator"}):
                LOGGER.info("[BT SG] Skipping subscriber article: %s", url)
                return False

            subscriber_text = soup.find(
                string=lambda text: text and "SUBSCRIBERS" in text.upper()
            )
            if subscriber_text:
                LOGGER.info("[BT SG] Skipping subscriber article (text match): %s", url)
                return False

            return True

        except Exception as error:
            LOGGER.error("[BT SG] Failed to check validity for %s: %s", url, error)
            return False

    def parse_articles(
        self,
        soup: BeautifulSoup,
        target_datetime: datetime,
        seen_urls: set,
    ) -> tuple[list, bool]:
        cards = soup.find_all("div", attrs={"data-testid": "basic-card-component"})

        if not cards:
            return [], False

        parsed_articles = []
        reached_older_date = False

        for card in cards:
            title_tag = card.find("h3", attrs={"data-testid": "card-title-component"})
            if not title_tag:
                continue

            link_tag = title_tag.find("a")
            if not link_tag:
                continue

            title = link_tag.get_text(strip=True)
            relative_url = link_tag.get("href", "")

            url = (
                f"https://www.businesstimes.com.sg{relative_url}"
                if relative_url.startswith("/")
                else relative_url
            )
            url = url.strip().rstrip(":")

            if not url or url in seen_urls:
                continue

            time_tag = card.find("div", attrs={"data-testid": "created-time-component"})
            raw_time = time_tag.get_text(strip=True) if time_tag else ""

            article_datetime = self.normalize_timestamp(raw_time)

            if not article_datetime:
                LOGGER.info("[BT SG] Failed to parse timestamp for %s. Skipping.", url)
                seen_urls.add(url)
                continue

            if article_datetime < target_datetime:
                reached_older_date = True
                break

            image_div = card.find("div", attrs={"data-testid": "card-image-v2-component"})
            img_tag = image_div.find("img") if image_div else None
            thumbnail = img_tag.get("src") if img_tag else None

            seen_urls.add(url)

            if not self.check_valid_article(url):
                continue

            parsed_articles.append({
                "title": title,
                "source": url,
                "thumbnail": thumbnail,
                "timestamp": article_datetime.strftime("%Y-%m-%d %H:%M:%S"),
            })

        return parsed_articles, reached_older_date

    def extract_news_pages(self, num_pages: int | None, target_date: str) -> list:
        target_datetime = datetime(
            int(target_date[:4]),
            int(target_date[4:6]),
            int(target_date[6:]),
            tzinfo=ZoneInfo("Asia/Singapore"),
        )

        base_urls = [
            "https://www.businesstimes.com.sg/keywords/sgx",
            'https://www.businesstimes.com.sg/singapore/economy-policy?ref=listing-menubar'
        ]

        for base_url in base_urls:
            soup = self.fetch_news_with_selenium(base_url)

            if soup is None:
                LOGGER.error("[BT SG] Failed to load initial page, aborting.")
                return self.articles

            seen_urls = set()
            scroll_count = 0

            while True:
                LOGGER.info("[BT SG] Scroll %d", scroll_count + 1)
                self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(4)

                current_soup = BeautifulSoup(self.driver.page_source, "html.parser")
                articles, reached_older_date = self.parse_articles(
                    current_soup, target_datetime, seen_urls
                )
                self.articles.extend(articles)

                if reached_older_date:
                    LOGGER.info("[BT SG] Reached articles older than %s, stopping.", target_date)
                    break

                scroll_count += 1

                if num_pages is not None and scroll_count >= num_pages:
                    LOGGER.info("[BT SG] Reached page limit of %d, stopping.", num_pages)
                    break

        LOGGER.info("[BT SG] Total scraped: %d", len(self.articles))
        return self.articles


def main():
    scraper = BusinessTimesSG()

    parser = argparse.ArgumentParser(description="Script for scraping data from Business Times SG")
    parser.add_argument("date", type=str)
    parser.add_argument("filename", type=str, nargs="?", default="businesstimes")
    parser.add_argument("--pages", type=int, default=5, help="Number of scrolls (default: 5)")
    parser.add_argument("--csv", action="store_true", help="Flag to indicate write to csv file")

    args = parser.parse_args()

    scraper.extract_news_pages(args.pages, args.date)
    scraper.write_json(scraper.articles, args.filename)

    if args.csv:
        scraper.write_csv(scraper.articles, args.filename)

    BusinessTimesSG.close_shared_driver()


if __name__ == "__main__":
    """
    How to run:
    uv run -m src.scraper_engine.sources.sgx.scrape_business_times <date> [filename] [--pages N] [--csv]

    Examples:
    uv run -m src.scraper_engine.sources.sgx.scrape_business_times 20260427
    uv run -m src.scraper_engine.sources.sgx.scrape_business_times 20260427 test_scrape_bt
    uv run -m src.scraper_engine.sources.sgx.scrape_business_times 20260427 test_scrape_bt --pages 5 --csv
    """
    main()
    