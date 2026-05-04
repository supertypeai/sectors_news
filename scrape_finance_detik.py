from datetime import datetime
from pathlib import Path 

from scraper_engine.base.scraper import Scraper

import argparse
import time
import logging 
import json 
import random 


class FinanceDetik(Scraper):
    def fetch_news(self, url: str):
        soup = self.fetch_news(url)

        article_items = soup.find_all("article", class_="list-content__item")
        
        return article_items 
    
    def parse_articles(self, article_items):
        output_path = Path("news.html")

        with output_path.open("w", encoding="utf-8") as file:
            file.write(str(article_items))

        for article_item in article_items:
            title_tag = article_item.find("h3", class_="media__title")
            title_link = title_tag.find("a") if title_tag else None

            title = title_link.get_text(strip=True) if title_link else None
            source_url = title_link["href"] if title_link else None

            thumbnail_tag = article_item.find("div", class_="media__image")
            thumbnail_img = thumbnail_tag.find("img") if thumbnail_tag else None
            thumbnail_url = thumbnail_img["src"] if thumbnail_img else None

            date_tag = article_item.find("div", class_="media__date")
            date_span = date_tag.find("span") if date_tag else None
            published_at = date_span["title"] if date_span else None 

            self.articles.append({
                "title": title,
                "source_url": source_url,
                "thumbnail_url": thumbnail_url,
                'timestamp': published_at
            })

        return self.articles

    def extract_news_pages(self, num_pages: int, date: str):
        base_url = 'https://finance.detik.com/bursa-dan-valas/indeks?' 
        year = date[:4]    
        month = date[4:6] 
        day = date[6:]

        page = 1 

        while True:
            params = f'page={page}date={day}%2F{month}%2F{year}'
            page_url = base_url + params 

            article_list = self.fetch_news(page_url)
            
            if not article_list: 
                print(f"[Finance Detik] No articles found on page {page}, stopping.")
                break

            articles = self.parse_articles(article_list)
            
            self.articles.extend(articles)

            if num_pages is not None and page >= num_pages: 
                break
            
            page += 1
            time.sleep(1)

        return self.articles
   
  
def main():
    scraper = FinanceDetik()

    parser = argparse.ArgumentParser(description="Script for scraping data from fianncialbisnis")
    parser.add_argument("page_number", type=int, default=1)
    parser.add_argument("date", type=str)
    parser.add_argument("filename", type=str, default="fianncialbisnis")
    parser.add_argument("--csv", action='store_true', help="Flag to indicate write to csv file")

    args = parser.parse_args()

    num_page = args.page_number
    date = args.date 

    scraper.extract_news_pages(num_page, date)

    scraper.write_json(scraper.articles, args.filename)

    if args.csv:
        scraper.write_csv(scraper.articles, args.filename)


if __name__ == "__main__":
  '''
  How to run:
  uv run -m src.scraper_engine.sources.idx.scrape_finance_detik <page_number> <filename_saved> <--csv (optional)>
  '''
  main()















if __name__ == '__main__':
    pass 