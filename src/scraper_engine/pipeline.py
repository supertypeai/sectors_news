from datetime import datetime, timezone, timedelta
from typing_extensions import Annotated

from scraper_engine.base.scraper_collection import ScraperCollection
from scraper_engine.base.scraper import SeleniumScraper

# from scraper_engine.sources.idx.scrape_idnfinancials import IDNFinancialScraper
# from scraper_engine.sources.idx.scrape_petromindo import PetromindoScraper
# from scraper_engine.sources.idx.scrape_insight_kontan import InsightKontanScraper
# from scraper_engine.sources.idx.scrape_mining import MiningScraper
# from scraper_engine.sources.idx.scrape_financial_bisnis import FinansialBisnisScraper

from scraper_engine.sources.idx.scrape_icn import ICNScraper
from scraper_engine.sources.idx.scrape_gapki import GapkiScraper
from scraper_engine.sources.idx.scrape_minerba import MinerbaScraper
from scraper_engine.sources.idx.scrape_abaf import AbafScraper
from scraper_engine.sources.idx.scrape_idnminer import IdnMinerScraper
from scraper_engine.sources.idx.scrape_jakartaglobe import JGScraper
from scraper_engine.sources.idx.scrape_antaranews import AntaraNewsScraper
from scraper_engine.sources.idx.scrape_asian_telekom import AsianTelekom
from scraper_engine.sources.idx.scrape_idn_business_post import IndonesiaBusinessPost
from scraper_engine.sources.idx.scrape_bca_news import run_scrape_bca_news
from scraper_engine.sources.idx.scrape_jakartapost import JakartaPost
from scraper_engine.sources.idx.scrape_kontan import KontanScraper
from scraper_engine.sources.idx.scrape_emiten_news import EmitenNews

from scraper_engine.sources.sgx.scrape_businesstimes import scrape_businesstimes 
from scraper_engine.sources.sgx.scrape_straitstimes import scrape_straitsnews_sgx

from .server import post_source
from scraper_engine.database.client import SUPABASE_CLIENT

import json
import os
import asyncio
import typer 
import sys
import logging


def setup_logging():
    """Configures logging for the whole application"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(name)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        handlers=[
            logging.StreamHandler(sys.stdout)
            # logging.FileHandler("scraper.log") 
        ]
    )


app = typer.Typer(
    help='A CLI for managing scraper News',
    no_args_is_help=True
)


@app.callback()
def main():
    """
    News Scraper CLI.
    
    This callback function treats this as a multi-command app
    """
    setup_logging()


@app.command(name="remove_outdated_news")
def delete_outdated_news(
    table_name: Annotated[str, typer.Option(help="Table name to deletes outdated news")],
):
    """
    Deletes news articles older than 120 days from the 'idx_news' table
    and saves (appends) the deleted items to a JSON file.
    """
    logger = logging.getLogger(__name__)

    try:
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=120)

        # 1. Fetch items older than 120 days
        response = (
            SUPABASE_CLIENT.table(table_name)
            .select("*")
            .lte("created_at", cutoff.isoformat())
            .execute()
        )
        items_to_delete = response.data or []

        # ensure data directory exists
        output_dir = "data"
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

            logger.info(
                f"Appended {len(items_to_delete)} items—now {len(combined)} total—in {filename}"
            )

            # 3. Uncomment to actually delete when ready:
            SUPABASE_CLIENT.table(table_name).delete().lte(
                "created_at", cutoff.isoformat()
            ).execute()
        else:
            logger.info("No outdated news items found for deletion.")

        logger.info(f"Outdated news deletion run completed at: {now.isoformat()}")

    except Exception as error:
        logger.error(f"Failed to delete or export outdated news: {error}")


@app.command(name="main_idx")
def main_idx(
    page_number: Annotated[int, typer.Option(help="Page number to scrape")] = 1,
    filename: Annotated[str, typer.Option(help="Output filename base")] = "pipeline",
    csv: Annotated[bool, typer.Option(help="Flag to write to CSV file")] = False,
    batch: Annotated[int, typer.Option(help="Batch number for processing")] = 1,
    batch_size: Annotated[int, typer.Option(help="Batch size for processing")] = 75,
    process_only: Annotated[bool, typer.Option(help="Only process, don't scrape")] = False,
    table_name: Annotated[str, typer.Option(help="Table name to push into db")] = 'idx_news',
    source_scraper: Annotated[str, typer.Option(help="Source scraper to define score prompt criteria")] = 'idx',
):
    """
    Main function to run the scraper collection (IDX News) and post results.
    """
    
    if not process_only:
        # idnscraper = IDNFinancialScraper()
        # petromindoscraper = PetromindoScraper()
        # insightkontanscraper = InsightKontanScraper()
        # miningscraper = MiningScraper()
        # finansialbisinisscraper = FinansialBisnisScraper()
        # idnbusinesspostscraper = IndonesiaBusinessPost()

        icnscraper = ICNScraper()
        gapkiscraper = GapkiScraper()
        minerbascraper = MinerbaScraper()
        abafscraper = AbafScraper()
        idnminerscraper = IdnMinerScraper()
        jgscraper = JGScraper()
        antaranewsscraper = AntaraNewsScraper()
        asiatelkomscraper = AsianTelekom()
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

            # Special flow for BCA News (Undetected Driver)
            parsed_bca_news = run_scrape_bca_news(page_number)

            scrapercollection.run_all(page_number)
            
            all_articles = scrapercollection.articles + parsed_bca_news

            scrapercollection.write_json(all_articles, source_scraper, filename)

            if csv:
                scrapercollection.write_csv(scrapercollection.articles, source_scraper, filename)

        finally:
            SeleniumScraper.close_shared_driver()

    asyncio.run(post_source(filename, batch, batch_size, table_name, source_scraper))


@app.command(name="main_sgx")
def main_sgx(
    page_number: Annotated[int, typer.Option(help="Page number to scrape")] = 1,
    filename: Annotated[str, typer.Option(help="Output filename base")] = "pipeline_sgx",
    csv: Annotated[bool, typer.Option(help="Flag to write to CSV file")] = False,
    batch: Annotated[int, typer.Option(help="Batch number for processing")] = 1,
    batch_size: Annotated[int, typer.Option(help="Batch size for processing")] = 75,
    process_only: Annotated[bool, typer.Option(help="Only process, don't scrape")] = False,
    table_name: Annotated[str, typer.Option(help="Table name to push into db")] = 'sgx_news',
    source_scraper: Annotated[str, typer.Option(help="Source scraper to define score prompt criteria")] = 'sgx',
):
    """
    Main function to run the scraper collection (SGX News) and post results.
    """
    
    if not process_only:
        # just need to use the method write json and csv
        scrapercollection = ScraperCollection()

        payload_business_times = scrape_businesstimes(page_number)
        payload_straitsnews = scrape_straitsnews_sgx(page_number)

        all_articles = payload_straitsnews + payload_business_times 

        scrapercollection.write_json(all_articles, source_scraper, filename)
        
        if csv:
            scrapercollection.write_csv(scrapercollection.articles, source_scraper, filename)

    asyncio.run(post_source(filename, batch, batch_size, table_name, source_scraper, is_sgx=True))


if __name__ == "__main__":
    app()


# uv pip install -e .
# uv run -m scraper_engine.pipeline main_sgx --page-number 2 --batch 1
# uv run -m scraper_engine.pipeline main_idx --page-number 2 --batch 1
