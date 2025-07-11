from concurrent.futures import ThreadPoolExecutor

from .news_model            import News 
from .extract_summary_news  import summarize_news
from .extract_score_news    import get_article_score
from database_management.database_connect import supabase, sectors_data, top300_data
from .extract_classifier import (
    get_tickers,
    get_tags_chat,
    get_subsector_chat,
    load_company_data,
    predict_dimension,
    get_sentiment_chat,
    NewsClassifier,
)

import asyncio
from datetime import datetime
import openai

CLASSIFIER = NewsClassifier()
EXECUTOR = ThreadPoolExecutor(max_workers=4)
COMPANY_DATA = load_company_data()


async def generate_article_async(data):
    """
    @helper-function
    @brief Generate article from URL asynchronously.
    @param data source URL and timestamp.
    @return Generated article in News model.
    """
    loop = asyncio.get_running_loop()
    source = data.get("source").strip()

    try:
        timestamp_str = data.get("timestamp").strip()
        timestamp_str = timestamp_str.replace("T", " ")
        timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")

        new_article = News(
            title="",
            body="",
            source=source,
            timestamp=timestamp.isoformat(),
            sector="",
            sub_sector=[],
            tags=[],
            tickers=[],
            dimension=None,
            score=None,
        )

        # Run synchronous summarize_news in a thread pool
        title, body = await loop.run_in_executor(EXECUTOR, summarize_news, source)

        if len(body) > 0:
            (
                tags,
                tickers,
                sub_sector_result,
                sentiment,
                dimension,
            ) = await CLASSIFIER.classify_article_async(title, body)

            if sentiment and len(sentiment) > 0:
                tags.append(sentiment[0])

            checked_tickers = []
            valid_tickers = [COMPANY_DATA[ticker]["symbol"] for ticker in COMPANY_DATA]
            for ticker in tickers:
                if ticker in valid_tickers or f"{ticker}.JK" in valid_tickers:
                    checked_tickers.append(ticker)
            tickers = checked_tickers

            if len(tickers) == 0 and sub_sector_result and len(sub_sector_result) > 0:
                sub_sector = [sub_sector_result[0].lower()]
            else:
                sub_sector = [
                    COMPANY_DATA[ticker]["sub_sector"]
                    for ticker in tickers
                    if ticker in COMPANY_DATA
                ]

            sector = ""
            for e in sub_sector:
                if e in sectors_data:
                    sector = sectors_data[e]
                    break

            new_article.title = title
            new_article.body = body
            new_article.sector = sector
            new_article.sub_sector = sub_sector
            new_article.tags = tags
            new_article.tickers = tickers
            new_article.dimension = dimension
            new_article.score = int(get_article_score(body, timestamp, datetime.now()))

        return new_article
    
    except openai.RateLimitError as limit:
            # Re-raise the error so the main loop can handle it
            raise limit
    
    except Exception as e:
        print(f"[ERROR] Error in generate_article_async for source {source}: {e}")
        return News(
            title="Error processing article",
            body=f"Failed to process article content from {source}",
            source=source,
            timestamp=datetime.now().isoformat(),
            sector="",
            sub_sector=[],
            tags=[],
            tickers=[],
            dimension=None,
            score=0,
        )


def generate_article(data):
    """
    @helper-function
    @brief Generate article from URL.

    @param data source URL and timestamp.

    @return Generated article in News model.
    """
    return asyncio.run(generate_article_async(data))