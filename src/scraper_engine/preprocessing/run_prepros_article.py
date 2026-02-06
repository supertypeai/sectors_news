from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from rapidfuzz import fuzz

from .news_model import News 
from .extract_summary_news import summarize_news, get_article_body
from .extract_score_news import get_article_score
from scraper_engine.database.metadata import get_sectors_data, build_ticker_index, build_sgx_ticker_index
from .extract_classifier import load_company_data, NewsClassifier, load_sub_sectors_data

import asyncio
import re
import logging


LOGGER = logging.getLogger(__name__)


CLASSIFIER = NewsClassifier()
EXECUTOR = ThreadPoolExecutor(max_workers=4)
COMPANY_DATA_IDX = load_company_data()
COMPANY_DATA_SGX = CLASSIFIER._load_sgx_company_data()
SUBSECTOR_DATA = load_sub_sectors_data()
TICKER_INDEX = build_ticker_index()
TICKER_INDEX_SGX = build_sgx_ticker_index()
SECTORS_DATA = get_sectors_data()


def matching_company_name(company_extracted: list[str], is_ticker: bool = True, is_sgx: bool = False) -> set:
    """
    Match extracted company identifiers against the company index.

    Args:
        company_extracted (list[str]): Extracted company names or tickers.
        is_ticker (bool): Match using ticker symbols if True, otherwise
            match using company names.
        is_sgx (bool): Use SGX-specific company index or rules if True.

    Returns:
        set: Set of matched company identifiers.
    """
    tickers = set()

    if is_sgx: 
        ticker_index = TICKER_INDEX_SGX
    else:
        ticker_index = TICKER_INDEX

    for company in company_extracted:
        company = re.sub(r'^\s*PT\s+', '', company, flags=re.IGNORECASE) 
        company = re.sub(r'\s*Tbk\.?$', '', company, flags=re.IGNORECASE)
        company = re.sub(r'\s*\(Persero\)\s*', ' ', company, flags=re.IGNORECASE)
        company = re.sub(r'\s+', ' ', company).strip().lower()
        
        ticker_found = None 
        if is_ticker:
            for company_name, ticker in ticker_index.items():
                ticker_lower = ticker.lower()
                ticker_lower = ticker_lower.replace('.jk', '').strip()
                best_match = fuzz.ratio(company, ticker_lower)
                
                if best_match > 95: 
                    ticker_found = ticker 
                    break
                
            if ticker_found:
                tickers.add(ticker_found)
        
        else: 
            for company_name, ticker in ticker_index.items():
                best_match = fuzz.ratio(company, company_name)
                
                if best_match > 95: 
                    ticker_found = ticker 
                    break
                else:
                    best_match_fallback = fuzz.partial_ratio(company, company_name)
                    if best_match_fallback > 95: 
                        ticker_found = ticker 
                        break 
                
            if ticker_found:
                tickers.add(ticker_found)
    
    return tickers


def post_processing(
    sentiment: str, 
    tags: list[str], 
    body: str, 
    title: str, 
    sub_sector_result: list[str], 
    dimension: dict, 
    url: str,
    is_sgx: bool = False
) -> dict[str, any]:
    """
    Enrich an article with derived metadata such as tickers,
    sector information, and dimensions.

    Args:
        sentiment (str): Article sentiment label.
        tags (list[str]): Article tags.
        body (str): Article body text.
        title (str): Article title.
        sub_sector_result (list[str]): Sub-sector classification output.
        dimension (dict): Dimension metadata.
        url (str): Article URL.
        is_sgx (bool): Apply SGX-specific processing if True.

    Returns:
        dict[str, any]: Post-processed article metadata.
    """
    companies_lookup = COMPANY_DATA_SGX if is_sgx else COMPANY_DATA_IDX 

    # Sentiment added to tag
    if sentiment != 'Not Applicable':
        tags.append(sentiment)
        
    # Get tickers new flow 
    if is_sgx:
        company_extracted = CLASSIFIER.extract_company_name(body, title, is_sgx=True, is_ticker=False)
        LOGGER.info(f'raw company: {company_extracted}')
        matched_tickers = matching_company_name(company_extracted, is_ticker=False, is_sgx=True) 
        checked_tickers = list(matched_tickers)
    else: 
        company_extracted = CLASSIFIER.extract_company_name(body, title, is_ticker=False)
        tickers = matching_company_name(company_extracted, is_ticker=False)

        # Fallback tickers not found, only for emitennews
        if not tickers:
            url_to_check = "https://emitennews.com/news/"
            if url_to_check in url:
                full_article =  get_article_body(url)
                company_extracted = CLASSIFIER.extract_company_name(full_article, title)
                tickers = matching_company_name(company_extracted)

        # Tickers checking with COMPANY_DATA
        checked_tickers = []
        if tickers:
            for raw_ticker in tickers:
                ticker = raw_ticker if raw_ticker.endswith('.JK') else raw_ticker + ".JK"
                # Checking the correct tickers
                if ticker in companies_lookup:
                    checked_tickers.append(ticker)

    # Sub sector
    if is_sgx:
        sub_sector = [sub_sector_result[0].lower()] if (
            sub_sector_result and 
            sub_sector_result[0].lower() in SUBSECTOR_DATA
        ) else []
    else:
        if not checked_tickers and sub_sector_result:
            sub_sector = [sub_sector_result[0].lower()] if (
                sub_sector_result and 
                sub_sector_result[0].lower() in SUBSECTOR_DATA
            ) else []
        else:
            sub_sector = {
                companies_lookup[ticker]["sub_sector"]
                for ticker in checked_tickers 
                if ticker in companies_lookup
            }
    
    sub_sector = list(sub_sector)

    # Sectors data 
    sector = None 
    
    for sub in sub_sector:
        if sub in SECTORS_DATA: 
            sector = SECTORS_DATA[sub]
            break

    return {
        "tickers": checked_tickers,
        "sub_sector": sub_sector,
        "sector": sector,
        "dimension": dimension
    }


async def generate_article_async(data: dict, source_scraper: str, is_sgx: bool = False):
    """
    Asynchronously generate an article object from source data.

    Args:
        data (dict): Source data containing at least a URL and timestamp.
        source_scraper (str): Identifier of the scraper source.
        is_sgx (bool): Apply SGX-specific parsing or logic if True.

    Returns:
        News: Generated article object.
    """
    loop = asyncio.get_running_loop()
    source = data.get("source").strip()
    
    try:
        article_url = data.get('source')
        timestamp_str = data.get("timestamp").strip().replace("T", " ")
        timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")

        # Sumamrize 
        summary_result = await loop.run_in_executor(EXECUTOR, summarize_news, source)
        if not summary_result:
            LOGGER.error(f"Summarization failed for {source}, failing article.")
            # Fail the whole process
            return None 
        
        title, body = summary_result
        
        # Second validation
        if not title or not body:
            LOGGER.error(f"Summarization failed resulted in an empty body or title for {source}.")
            return None

        # Classify
        classification_results = await CLASSIFIER.classify_article_async(title, body)
        if not classification_results:
            LOGGER.error(f"Classification failed for {source}, failing article.")
            # Fail the whole process
            return None 
        tags, sub_sector_result, sentiment, dimension = classification_results

        # Score
        score_result = get_article_score(body, timestamp, source, source_scraper)

        # Assemble the final News object
        new_article = News(
            title=title, body=body, source=source, timestamp=timestamp.isoformat(),
            score=score_result, tags=tags, tickers=[], sub_sector=[], sector="",
            dimension=None
        )

        # Post-processing
        post_process_result = post_processing(
            sentiment, tags, body, 
            title, sub_sector_result, dimension, 
            article_url, is_sgx
        )
        new_article.tickers = post_process_result.get("tickers")
        new_article.sub_sector = post_process_result.get("sub_sector")
        new_article.sector = post_process_result.get("sector")
        new_article.dimension = post_process_result.get("dimension")
        
        return new_article

    except Exception as error: 
        LOGGER.error(
            f"[ERROR] A critical, unexpected error occurred in generate_article_async for {source}: {error}",
            exc_info=True
        )
        return None

 
def generate_article(data: dict[str], source_scraper: str):
    """
    @helper-function
    @brief Generate article from URL.

    @param data source URL and timestamp.

    @return Generated article in News model.
    """
    return asyncio.run(generate_article_async(data, source_scraper))