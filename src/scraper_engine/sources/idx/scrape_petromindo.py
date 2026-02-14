from scraper_engine.base.scraper import Scraper

import argparse
import locale
import dateparser
import logging


locale.setlocale(locale.LC_TIME, "en_US.UTF-8")

LOGGER = logging.getLogger(__name__)


class PetromindoScraper(Scraper):
    categories = [
        'oil-gas',
        'electricity-renewables-carbon',
        'coal',
        'minerals'
    ]

    def extract_news(self, category, url):
        soup = self.fetch_news(url)
        for item in soup.find_all('article'):
            div = item.find('div', class_='highlight-content')
            if div:
                title = (
                    div.find('h3', class_='highlight-title')
                    .text.strip()
                )
                # body = item.find('p', class_='summary').text
                source = (
                    item.find('a', class_='highlight-link')
                    ['href']
                    .strip()
                )
                timestamp = (
                    div.find('div', class_='highlight-meta')
                    .find('span', class_='posted')
                    .text.strip()
                )
                timestamp = dateparser.parse(
                    timestamp
                ).strftime("%Y-%m-%d %H:%M:%S")

                self.articles.append(
                    {
                        'title': title,
                        'source': source,
                        'timestamp': timestamp,
                        'category': category
                    }
                )
        
        LOGGER.info(f'total scraped source of petromindo: {len(self.articles)}')
        return self.articles

    def extract_news_pages(self, num_pages):
        for category in self.categories:
            self.extract_news_pages_category(
                category,
                num_pages
            )
        return self.articles

    def extract_news_pages_category(
        self,
        category,
        num_pages
    ):
        for index in range(num_pages):
            self.extract_news(
                category,
                self.get_page(category, index)
            )
        return self.articles

    def get_page(self, category, page_num):
        return (
            f'https://www.petromindo.com/news/category/'
            f'{category}?page={page_num}'
        )


def main():
    scraper = PetromindoScraper()

    parser = argparse.ArgumentParser(
        description="Script for scraping data from petromindo"
    )
    parser.add_argument("category", type=int, default=0)
    # 0: 'oil-gas', 1: 'electricity-renewables-carbon', 2: 'coal', 3: 'minerals'
    parser.add_argument("page_number", type=int, default=1)
    parser.add_argument("filename", type=str, default="petromindoarticles")
    parser.add_argument(
        "--csv",
        action='store_true',
        help="Flag to indicate write to csv file"
    )

    args = parser.parse_args()

    num_page = args.page_number
    category = args.category

    scraper.extract_news_pages(
        scraper.categories[category],
        num_page
    )

    scraper.write_json(scraper.articles, args.filename)

    if args.csv:
        scraper.write_csv(scraper.articles, args.filename)


if __name__ == "__main__":
    '''
    How to run:
    python scrape_petromindo.py <category> <page_number> <filename_saved> <--csv (optional)>
    0: 'oil-gas', 1: 'electricity-renewables-carbon', 2: 'coal', 3: 'minerals'
    '''
    main()
