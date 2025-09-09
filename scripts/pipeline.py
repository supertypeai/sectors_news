import sys
import os
import argparse

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from base_model.scraper_collection      import ScraperCollection
from base_model.scraper                 import SeleniumScraper
from models.scrape_idnfinancials        import IDNFinancialScraper
from models.scrape_petromindo           import PetromindoScraper
from models.scrape_icn                  import ICNScraper
from models.scrape_gapki                import GapkiScraper
from models.scrape_minerba              import MinerbaScraper
from models.scrape_abaf                 import AbafScraper
from models.scrape_insight_kontan       import InsightKontanScraper
from models.scrape_idnminer             import IdnMinerScraper
from models.scrape_jakartaglobe         import JGScraper
from scripts.server                     import post_source
from models.scrape_mining               import MiningScraper
from models.scrape_antaranews           import AntaraNewsScraper
from models.scrape_asian_telekom        import AsianTelekom
from models.scrape_financial_bisnis     import FinansialBisnisScraper
from models.scrape_idn_business_post    import IndonesiaBusinessPost
from models.scrape_jakartapost          import JakartaPost 
from models.scrape_kontan               import KontanScraper
from models.scrape_emiten_news          import EmitenNews
from config.setup                       import SUPABASE_KEY, SUPABASE_URL, LOGGER

import json
from supabase import create_client, Client
from datetime import datetime, timezone, timedelta


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

            LOGGER.info(
                f"Appended {len(items_to_delete)} items—now {len(combined)} total—in {filename}"
            )

            # 3. Uncomment to actually delete when ready:
            supabase.table("idx_news").delete().lte(
                "created_at", cutoff.isoformat()
            ).execute()
        else:
            LOGGER.info("No outdated news items found for deletion.")

        LOGGER.info(f"Outdated news deletion run completed at: {now.isoformat()}")

    except Exception as e:
        LOGGER.error(f"Failed to delete or export outdated news: {e}")


def main():
    """ 
    Main function to run the scraper collection and post the results.
    It initializes the scrapers, runs them, and posts the scraped articles to the server.
    """
    parser = argparse.ArgumentParser(
            description="Script for scraping data with pipeline"
        )
    parser.add_argument("page_number", type=int, default=1)
    parser.add_argument("filename", type=str, default="scraped_articles")
    parser.add_argument(
        "--csv", action="store_true", help="Flag to indicate write to csv file"
    )
    parser.add_argument('--batch', type=int, default=1)
    parser.add_argument('--batch-size', type=int, default=75)
    parser.add_argument('--process-only', action="store_true", help="Only process, don't scrape")
    
    args = parser.parse_args()
    
    if not args.process_only:
        # idnscraper = IDNFinancialScraper()
        # petromindoscraper = PetromindoScraper()
        icnscraper = ICNScraper()
        gapkiscraper = GapkiScraper()
        minerbascraper = MinerbaScraper()
        abafscraper = AbafScraper()
        # insightkontanscraper = InsightKontanScraper()
        idnminerscraper = IdnMinerScraper()
        jgscraper = JGScraper()
        # miningscraper = MiningScraper()
        antaranewsscraper = AntaraNewsScraper()
        asiatelkomscraper = AsianTelekom()
        # finansialbisinisscraper = FinansialBisnisScraper()
        idnbusinesspostscraper = IndonesiaBusinessPost()
        jakartapostscraper = JakartaPost()
        kontanarticlescraper = KontanScraper()
        emitenscraper = EmitenNews()

        try:
            scrapercollection = ScraperCollection()
            # scrapercollection.add_scraper(idnscraper)
            # scrapercollection.add_scraper(petromindoscraper)
            # scrapercollection.add_scraper(finansialbisinisscraper)
            # scrapercollection.add_scraper(idnbusinesspostscraper)
            # scrapercollection.add_scraper(insightkontanscraper) 
            # Insider specific, should be filtered to go inside insider db
            # scrapercollection.add_scraper(miningscraper)
            
            scrapercollection.add_scraper(icnscraper)
            scrapercollection.add_scraper(gapkiscraper)
            scrapercollection.add_scraper(minerbascraper)
            scrapercollection.add_scraper(abafscraper)
            scrapercollection.add_scraper(idnminerscraper)
            scrapercollection.add_scraper(jgscraper)
            scrapercollection.add_scraper(antaranewsscraper)
            scrapercollection.add_scraper(asiatelkomscraper)
            scrapercollection.add_scraper(jakartapostscraper)
            scrapercollection.add_scraper(kontanarticlescraper)
            scrapercollection.add_scraper(emitenscraper)

            num_page = args.page_number

            scrapercollection.run_all(num_page)

            scrapercollection.write_json(scrapercollection.articles, args.filename)

            if args.csv:
                scrapercollection.write_csv(scrapercollection.articles, args.filename)

        finally:
            SeleniumScraper.close_shared_driver()

    post_source(args.filename, args.batch, args.batch_size)


if __name__ == "__main__":
    main()
    delete_outdated_news()

# python scripts/pipeline.py page_num filename --csv
