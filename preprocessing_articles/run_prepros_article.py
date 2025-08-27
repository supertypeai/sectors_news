from concurrent.futures import ThreadPoolExecutor

from .news_model                import News 
from .extract_summary_news      import summarize_news
from .extract_score_news        import get_article_score
from database.database_connect  import sectors_data
from .extract_classifier        import load_company_data, NewsClassifier
from config.setup               import LOGGER

import asyncio
from datetime import datetime


CLASSIFIER = NewsClassifier()
EXECUTOR = ThreadPoolExecutor(max_workers=4)
COMPANY_DATA = load_company_data()


def get_ticker_manual(title: str, body: str, company_data: dict) -> list[str]:
    """ 
    Get ticker manually by matching company names in the title and body.
    
    Args:
        title (str): The title of the article.
        body (str): The body of the article.
        company_data (dict): Dictionary of company data with tickers as keys.

    Returns:
        list[str]: List of matched tickers.
    """
    full_text = f"{title} {body}".lower()
    matched_tickers = []

    for ticker, company_info in company_data.items():
        company_name = company_info.get('name').lower()
        company_words = [word for word in company_name.split() 
                        if len(word) > 2 and word not in ['tbk', 'ltd', 'inc', 'corp']]
        
        # Check if any company word is in the text
        if any(word in full_text for word in company_words):
            matched_tickers.append(ticker)
    
    return matched_tickers


async def generate_article_async(data: dict):
    """
    @helper-function
    @brief Generate article from URL asynchronously.
    @param data source URL and timestamp.
    @return Generated article in News model.
    """
    loop = asyncio.get_running_loop()
    source = data.get("source").strip()
    
    try:
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
        tags, tickers, sub_sector_result, sentiment, dimension = classification_results

        # Score
        score_result = get_article_score(body, timestamp, source)

        # Assemble the final News object
        new_article = News(
            title=title, body=body, source=source, timestamp=timestamp.isoformat(),
            score=score_result, tags=tags, tickers=[], sub_sector=[], sector="",
            dimension=None
        )

        # Post-processing
        # sentiment added into tags
        if sentiment:
            tags.append(sentiment)
        
        # Tickers checking with COMPANY_DATA
        checked_tickers = []
        if not tickers:
            tickers = get_ticker_manual(title, body, COMPANY_DATA)

        for raw_ticker in tickers:
            # Normalize tickers to have .JK
            ticker = raw_ticker if raw_ticker.endswith('.JK') else raw_ticker + ".JK"
            # Checking the correct tickers
            if ticker in COMPANY_DATA:
                checked_tickers.append(ticker)
        new_article.tickers = checked_tickers

        # Sub sector
        if not checked_tickers and sub_sector_result:
            new_article.sub_sector = [sub_sector_result[0].lower()] if sub_sector_result else []
        else:
            new_article.sub_sector = [COMPANY_DATA[ticker]["sub_sector"] for ticker in checked_tickers if ticker in COMPANY_DATA]

        # Sectors data 
        for sub in new_article.sub_sector:
            if sub in sectors_data: 
                new_article.sector = sectors_data[sub]
                break
        
        new_article.dimension = dimension

        return new_article

    except Exception as error: 
        LOGGER.error(f"[ERROR] A critical, unexpected error occurred in generate_article_async for {source}: {error}")
        return None

 
def generate_article(data: dict):
    """
    @helper-function
    @brief Generate article from URL.

    @param data source URL and timestamp.

    @return Generated article in News model.
    """
    return asyncio.run(generate_article_async(data))