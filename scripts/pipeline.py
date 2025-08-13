import sys
import os
import argparse

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from base_model.scraper_collection  import ScraperCollection
from models.scrape_idnfinancials    import IDNFinancialScraper
from models.scrape_petromindo       import PetromindoScraper
from models.scrape_icn              import ICNScraper
from models.scrape_gapki            import GapkiScraper
from models.scrape_minerba          import MinerbaScraper
from models.scrape_abaf             import AbafScraper
from models.scrape_kontan           import KontanScraper
from models.scrape_idnminer         import IdnMinerScraper
from models.scrape_jakartaglobe     import JGScraper
from scripts.server                 import post_source
from models.scrape_mining           import MiningScraper
from config.setup                   import SUPABASE_KEY, SUPABASE_URL

import json
from supabase   import create_client, Client
from datetime   import datetime, timezone, timedelta


if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("Missing SUPABASE_URL or SUPABASE_ANON_KEY in environment")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


def delete_outdated_news():
    """
    Deletes news articles older than 120 days from the 'idx_news' table
    and saves (appends) the deleted items to a JSON file.
    """
    try:
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=120)

        # 1. Fetch items older than 120 days
        response = (
            supabase.table("idx_news")
            .select("*")
            .lte("created_at", cutoff.isoformat())
            .execute()
        )
        items_to_delete = response.data or []

        # ensure data directory exists
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        output_dir = os.path.join(project_root, "data")
        os.makedirs(output_dir, exist_ok=True)

        filename = os.path.join(output_dir, "outdated_news.json")

        if items_to_delete:
            # load existing records if file exists, else start fresh
            if os.path.exists(filename):
                with open(filename, "r") as f:
                    existing = json.load(f)
                # make sure it's a list
                if not isinstance(existing, list):
                    existing = []
            else:
                existing = []

            # append new items and write back
            combined = existing + items_to_delete
            with open(filename, "w") as f:
                json.dump(combined, f, indent=4)

            print(
                f"Appended {len(items_to_delete)} items—now {len(combined)} total—in {filename}"
            )

            # 3. Uncomment to actually delete when ready:
            supabase.table("idx_news").delete().lte(
                "created_at", cutoff.isoformat()
            ).execute()
        else:
            print("No outdated news items found for deletion.")

        print(f"Outdated news deletion run completed at: {now.isoformat()}")

    except Exception as e:
        print(f"Failed to delete or export outdated news: {e}")


def main():
    """ 
    Main function to run the scraper collection and post the results.
    It initializes the scrapers, runs them, and posts the scraped articles to the server.
    """
    idnscraper = IDNFinancialScraper()
    petromindoscraper = PetromindoScraper()
    icnscraper = ICNScraper()
    gapkiscraper = GapkiScraper()
    minerbascraper = MinerbaScraper()
    abafscraper = AbafScraper()
    kontanscraper = KontanScraper()
    idnminerscraper = IdnMinerScraper()
    jgscraper = JGScraper()
    miningscraper = MiningScraper()

    try:
        scrapercollection = ScraperCollection()
        # scrapercollection.add_scraper(idnscraper)
        # scrapercollection.add_scraper(petromindoscraper)
        scrapercollection.add_scraper(icnscraper)
        scrapercollection.add_scraper(gapkiscraper)
        scrapercollection.add_scraper(minerbascraper)
        scrapercollection.add_scraper(abafscraper)
        # scrapercollection.add_scraper(kontanscraper)
        scrapercollection.add_scraper(idnminerscraper)
        scrapercollection.add_scraper(jgscraper)
        # Insider specific, should be filtered to go inside insider db
        # scrapercollection.add_scraper(miningscraper)

        parser = argparse.ArgumentParser(
            description="Script for scraping data with pipeline"
        )
        parser.add_argument("page_number", type=int, default=1)
        parser.add_argument("filename", type=str, default="scraped_articles")
        parser.add_argument(
            "--csv", action="store_true", help="Flag to indicate write to csv file"
        )

        args = parser.parse_args()

        num_page = args.page_number

        scrapercollection.run_all(num_page)

        scrapercollection.write_json(scrapercollection.articles, args.filename)

        if args.csv:
            scrapercollection.write_csv(scrapercollection.articles, args.filename)

    finally:
        gapkiscraper.close_driver()

    post_source(args.filename)


if __name__ == "__main__":
    main()
    delete_outdated_news()

# python scripts/pipeline.py page_num filename --csv
