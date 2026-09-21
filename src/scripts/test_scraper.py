from scraper_engine.base.scraper_collection import ScraperCollection
from scraper_engine.sources.idx.scrape_investor_id import InvestorID
from scraper_engine.sources.idx.scrape_cnbc_market import CNBCMarket
from scraper_engine.sources.idx.scrape_cnn_ekonomi import CNNEkonomi
from scraper_engine.sources.idx.scrape_kontan_investasi import KontanInvestasi
from scraper_engine.sources.idx.scrape_kontan_keuangan import KontanKeuangan

import json 
import logging 


def test_scraper():
    """
    Test only sources that get ip blacklisted in dagu runner.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    
    investor_id_scraper = InvestorID()
    cnbc_market_scraper = CNBCMarket()
    cnn_ekonomi_scraper = CNNEkonomi()
    kontan_investasi_scraper = KontanInvestasi()
    kontan_keuangan_scraper = KontanKeuangan()

    scraper_collection = ScraperCollection()
    scraper_collection.add_scraper(investor_id_scraper)
    scraper_collection.add_scraper(cnbc_market_scraper)
    scraper_collection.add_scraper(cnn_ekonomi_scraper)
    scraper_collection.add_scraper(kontan_investasi_scraper)
    scraper_collection.add_scraper(kontan_keuangan_scraper)

    all_articles = scraper_collection.run_all(
        num_page=1,
        date=None,
        filter_from=None,
        is_use_proxy=False,
    )

    logging.info(
        "Scraped articles:\n%s", 
        json.dumps(all_articles[:10], indent=2)
    )

    
if __name__ == "__main__":
    test_scraper()
