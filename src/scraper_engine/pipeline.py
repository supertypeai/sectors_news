from datetime import datetime, timezone, timedelta
from typing_extensions import Annotated, Optional
from pathlib import Path
from zoneinfo import ZoneInfo

from scraper_engine.base.scraper_collection import ScraperCollection
from scraper_engine.base.scraper import SeleniumScraper

# from scraper_engine.sources.idx.scrape_petromindo import PetromindoScraper
# from scraper_engine.sources.idx.scrape_insight_kontan import InsightKontanScraper
# from scraper_engine.sources.idx.scrape_mining import MiningScraper
# from scraper_engine.sources.idx.scrape_idn_business_post import IndonesiaBusinessPost

from scraper_engine.sources.idx.scrape_icn import ICNScraper
from scraper_engine.sources.idx.scrape_gapki import GapkiScraper
from scraper_engine.sources.idx.scrape_minerba import MinerbaScraper
from scraper_engine.sources.idx.scrape_idnminer import IdnMinerScraper
from scraper_engine.sources.idx.scrape_idnfinancials import IDNFinancialScraper
from scraper_engine.sources.idx.scrape_bisnis_com import BisnisMarket
from scraper_engine.sources.idx.scrape_abaf import AbafScraper
from scraper_engine.sources.idx.scrape_jakartaglobe import JakartaGlobe
from scraper_engine.sources.idx.scrape_antaranews import AntaraNews
from scraper_engine.sources.idx.scrape_asian_telekom import AsianTelecom
from scraper_engine.sources.idx.scrape_bca_news import BCANews
from scraper_engine.sources.idx.scrape_jakartapost import JakartaPost
from scraper_engine.sources.idx.scrape_kontan_investasi import KontanInvestasi
from scraper_engine.sources.idx.scrape_emiten_news import EmitenNews
from scraper_engine.sources.idx.scrape_investor_id import InvestorID
from scraper_engine.sources.idx.scrape_bloomberg_technoz import BloombergTechnoz
from scraper_engine.sources.idx.scrape_cnbc_market import CNBCMarket 
from scraper_engine.sources.idx.scrape_cnn_ekonomi import CNNEkonomi
from scraper_engine.sources.idx.scrape_kontan_keuangan import KontanKeuangan
from scraper_engine.sources.idx.scrape_finance_detik import FinanceDetik
from scraper_engine.sources.idx.scrape_kompas import KompasMoney

from scraper_engine.sources.sgx.scrape_business_times import BusinessTimesSG 
from scraper_engine.sources.sgx.scrape_straits_times import StraitsTimes
from scraper_engine.sources.sgx.scrape_cna import ChannelNewsAsiaSG
from scraper_engine.sources.sgx.scrape_sbr_sg import SBRSG

from .processor import post_source
from scraper_engine.database.client import SUPABASE_CLIENT

import json
import os
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
    source_scraper: Annotated[str, typer.Option(help="Source scraper to define score prompt criteria")] = 'idx'
):
    """
    Deletes news articles older than 120 days from the 'idx_news and sgx_news' table
    and saves (appends) the deleted items to a JSON file.
    """
    logger = logging.getLogger(__name__)

    try:
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(days=120)

        response = (
            SUPABASE_CLIENT.table(table_name)
            .select("*")
            .lte("created_at", cutoff.isoformat())
            .execute()
        )

        items_to_delete = response.data or []

        output_path = Path("data") / ("outdated_news.json" if source_scraper == "idx" else f"outdated_news_{source_scraper}.json")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        if items_to_delete: 
            existing = []

            if output_path.exists():
                try:
                    with output_path.open("r") as file:
                        data = json.load(file)
                        existing = data if isinstance(data, list) else []

                except Exception as error:
                    logger.warning(
                        "Failed to read existing outdated file: %s. Starting fresh.", error
                    )

            combined = existing + items_to_delete

            with output_path.open("w") as file:
                json.dump(combined, file, indent=4)

            logger.info(
                "Appended %d items — now %d total — in %s",
                len(items_to_delete),
                len(combined),
                output_path,
            )

            SUPABASE_CLIENT.table(table_name).delete().lte(
                "created_at", cutoff.isoformat()
            ).execute()

        else:
            logger.info("No outdated articles found in %s.", table_name)

        logger.info("Outdated news deletion completed at %s.", now.isoformat())

    except Exception as error:
        logger.error("Failed to delete or export outdated news: %s", error)


@app.command(name="main_idx")
def main_idx(
    page_number: Annotated[int | None, typer.Option(help="Page number to scrape")] = None,
    filename: Annotated[str, typer.Option(help="Output filename base")] = "pipeline",
    csv: Annotated[bool, typer.Option(help="Flag to write to CSV file")] = False,
    batch: Annotated[int, typer.Option(help="Batch number for processing")] = 1,
    batch_size: Annotated[int, typer.Option(help="Batch size for processing")] = 75,
    process_only: Annotated[bool, typer.Option(help="Only process, don't scrape")] = False,
    table_name: Annotated[str, typer.Option(help="Table name to push into db")] = 'idx_news',
    source_scraper: Annotated[str, typer.Option(help="Source scraper to define score prompt criteria")] = 'idx',
    date:  Annotated[Optional[str], typer.Option(help="End date: YYYYMMDD")] = None
):
    """
    Main function to run the scraper collection (IDX News) and post results.
    """
    last_state_path = Path('data/last_state.json')

    last_state = {}
    try:
        with last_state_path.open('r') as file:
            last_state = json.load(file)

    except (FileNotFoundError, json.JSONDecodeError):
        pass
    
    wib = ZoneInfo("Asia/Jakarta")

    if date:
        filter_from = datetime.strptime(date, "%Y%m%d").replace(tzinfo=wib)
    
    elif last_state.get("last_run_at"):
        filter_from = datetime.fromisoformat(last_state["last_run_at"])
    
    else:
        filter_from = datetime.now(wib) - timedelta(days=1)

    if not process_only:
        # petromindoscraper = PetromindoScraper()
        # insightkontanscraper = InsightKontanScraper()
        # miningscraper = MiningScraper()
        # idnbusinesspostscraper = IndonesiaBusinessPost()

        # icnscraper = ICNScraper()
        # gapkiscraper = GapkiScraper()
        # minerbascraper = MinerbaScraper()
        # idnminerscraper = IdnMinerScraper()
        idnscraper = IDNFinancialScraper()
        finansialbisinisscraper = BisnisMarket()
        bloombertechnoz = BloombergTechnoz()
        investorid = InvestorID()
        abafscraper = AbafScraper()
        jgscraper = JakartaGlobe()
        antaranewsscraper = AntaraNews()
        asiatelkomscraper = AsianTelecom()
        jakartapostscraper = JakartaPost()
        kontanarticlescraper = KontanInvestasi()
        emitenscraper = EmitenNews()
        bcanews = BCANews()
        cnbcmarket = CNBCMarket()
        cnnekonomi = CNNEkonomi()
        kompasmoney = KompasMoney()
        financedetik = FinanceDetik()
        kontankeuangan = KontanKeuangan()

        try:
            scrapercollection = ScraperCollection()
            # scrapercollection.add_scraper(idnscraper)
            # scrapercollection.add_scraper(petromindoscraper)
            # scrapercollection.add_scraper(idnbusinesspostscraper)
            # scrapercollection.add_scraper(insightkontanscraper) 
            # scrapercollection.add_scraper(miningscraper)

            # scrapercollection.add_scraper(icnscraper)
            # scrapercollection.add_scraper(gapkiscraper)
            # scrapercollection.add_scraper(minerbascraper)
            # scrapercollection.add_scraper(idnminerscraper)
            scrapercollection.add_scraper(idnscraper)
            scrapercollection.add_scraper(finansialbisinisscraper)
            scrapercollection.add_scraper(bloombertechnoz)
            scrapercollection.add_scraper(investorid)
            scrapercollection.add_scraper(abafscraper)
            scrapercollection.add_scraper(jgscraper)
            scrapercollection.add_scraper(antaranewsscraper)
            scrapercollection.add_scraper(asiatelkomscraper)
            scrapercollection.add_scraper(jakartapostscraper)
            scrapercollection.add_scraper(kontanarticlescraper)
            scrapercollection.add_scraper(emitenscraper)
            scrapercollection.add_scraper(bcanews)
            scrapercollection.add_scraper(cnbcmarket)
            scrapercollection.add_scraper(cnnekonomi)
            scrapercollection.add_scraper(kompasmoney)
            scrapercollection.add_scraper(financedetik)
            scrapercollection.add_scraper(kontankeuangan)

            with last_state_path.open('w') as file:
                json.dump({"last_run_at": datetime.now(wib).isoformat()}, file)

            scrapercollection.run_all(page_number, date, filter_from)
            
            all_articles = scrapercollection.articles

            scrapercollection.write_json(all_articles, source_scraper, filename)

            if csv:
                scrapercollection.write_csv(all_articles, source_scraper, filename)

        finally:
            SeleniumScraper.close_shared_driver()

    post_source(filename, batch, batch_size, table_name, source_scraper, filter_from)


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
    date:  Annotated[Optional[str], typer.Option(help="End date: YYYYMMDD")] = None
):
    """
    Main function to run the scraper collection (SGX News) and post results.
    """
    last_state_path = Path('data/last_state_sgx.json')

    last_state = {}
    try:
        with last_state_path.open('r') as file:
            last_state = json.load(file)

    except (FileNotFoundError, json.JSONDecodeError):
        pass
    
    sgt = ZoneInfo("Asia/Singapore")

    if date:
        filter_from = datetime.strptime(date, "%Y%m%d").replace(tzinfo=sgt)
    
    elif last_state.get("last_run_at"):
        filter_from = datetime.fromisoformat(last_state["last_run_at"])
    
    else:
        filter_from = datetime.now(sgt) - timedelta(days=1)

    if not process_only:
        businesstimesscraper = BusinessTimesSG()
        straitstimesscraper = StraitsTimes()
        channelnewsasiascraper = ChannelNewsAsiaSG()
        sbrsg_scraper = SBRSG()

        try:
            scrapercollection = ScraperCollection()
            scrapercollection.add_scraper(businesstimesscraper)
            scrapercollection.add_scraper(straitstimesscraper)
            scrapercollection.add_scraper(channelnewsasiascraper)
            scrapercollection.add_scraper(sbrsg_scraper)

            with last_state_path.open('w') as file:
                json.dump({"last_run_at": datetime.now(sgt).isoformat()}, file)

            scrapercollection.run_all(page_number, date, filter_from)

            all_articles = scrapercollection.articles

            scrapercollection.write_json(all_articles, source_scraper, filename)

            if csv:
                scrapercollection.write_csv(all_articles, source_scraper, filename)

        finally:
            SeleniumScraper.close_shared_driver()

    post_source(filename, batch, batch_size, table_name, source_scraper, filter_from)


if __name__ == "__main__":
    app()


# uv pip install -e .
# uv run -m scraper_engine.pipeline main_sgx --page-number 2 --batch 1
# uv run -m scraper_engine.pipeline main_idx --page-number 2 --batch 1
