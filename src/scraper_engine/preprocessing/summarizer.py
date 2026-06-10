from goose3                         import Goose
from langchain_core.output_parsers  import JsonOutputParser
from langchain.prompts              import ChatPromptTemplate

from scraper_engine.llm.client   import get_llm, TokenUsageLogger
from scraper_engine.llm.prompts  import SummarizationPrompts, SummaryNews
from scraper_engine.config.conf  import USER_AGENT, MODEL_NAMES
from .article_fetcher            import extract_table_content

import re
import cloudscraper
import time 
import logging


LOGGER = logging.getLogger(__name__)


def basic_cleaning_body(body: str) -> str:
    """ 
    Basic cleaning of the body text to remove any word 'ticker' mentions in parentheses.

    Args:
        body (str): The body text to be cleaned.
    
    Returns:
        str: The cleaned body text.
    """
    body = re.sub(r'\([^)]*ticker[^)]*\)', '', body, flags=re.IGNORECASE)
    body = re.sub(r'\s+', ' ', body)
    body = body.strip()
    return body


def clean_apostrophe_case(body: str) -> str:
    """
    Finds an apostrophe followed by any uppercase letter
    at the end of a word and converts that letter to lowercase.
    
    Handles both straight (') and smart (’) quotes.
    
    Args:
        body (str): The body text to be cleaned.
    
    Returns:
        str: The cleaned body text.
    """
    pattern = r"(’|')([A-Z])\b"
    
    def replacer(match):
        quote = match.group(1) 
        letter = match.group(2).lower()
        return quote + letter
        
    return re.sub(pattern, replacer, body)


def normalize_company_abbreviations(body: str) -> str:
    """
    Safely finds all "Pt." or "Pt" abbreviations and capitalizes them to "PT".
    This is safe to run on a whole paragraph.

    Args:
        body (str): The body text to be cleaned.
    
    Returns:
        str: The cleaned body text.
    """
    # Fix "Pt." -> "PT" (case-insensitive)
    cleaned_body = re.sub(r"\bPt\.?\b", "PT", body, flags=re.IGNORECASE)
    
    # Fix "tbk" -> "Tbk" (case-insensitive)
    cleaned_body = re.sub(r"\bTbk\b", "Tbk", cleaned_body, flags=re.IGNORECASE)
    
    return cleaned_body


def normalize_dot_case(body: str) -> str:
    """
    Finds Indonesian-style thousands separators (dots) 
    and converts them to English-style (commas) to match
    the standard (e.g., 54.110.800 -> 54,110,800).
    
    Args:
        body (str): The body text to be cleaned.
    
    Returns:
        str: The cleaned body text.
    """
    pattern_thousands = r"(\d)\.(\d{3})(?!%)"
    
    while re.search(pattern_thousands, body):
        body = re.sub(pattern_thousands, r"\1,\2", body)

    pattern_decimals = r"(\d),(\d{1,2})(?![\d,])"
    body = re.sub(pattern_decimals, r"\1.\2", body)
    
    return body


def summarize_article(title: str, body: str, url: str) -> dict[str]:
    prompts = SummarizationPrompts()

    user_prompt = prompts.get_user_prompt()
    system_prompt = prompts.get_system_prompt() 

    summary_parser = JsonOutputParser(pydantic_object=SummaryNews)
    format_instructions = summary_parser.get_format_instructions()
    
    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ('user', user_prompt )
    ])
    
    input_data = {
        "title": title,
        "article": body,
        'format_instructions': format_instructions
    }
    
    for model in MODEL_NAMES:
        try:
            llm = get_llm(model, temperature=0.15)
            LOGGER.info(f"LLM used: {model}")

            summary_chain = prompt | llm | summary_parser
            
            summary_result = summary_chain.invoke(
                input_data, 
                config={"callbacks": [TokenUsageLogger()]}
            )

            if summary_result is None:
                LOGGER.warning("API call failed after all retries, trying next LLM...")
                continue

            if not summary_result.get("title") or not summary_result.get("summary"):
                LOGGER.info("[ERROR] LLM returned incomplete summary_result")
                continue
            
            LOGGER.info(f"[SUCCES] Summarize for url: {url}")
            return summary_result
            
        except Exception as error:
            LOGGER.warning(f"LLM failed with error: {error}")
            continue 

    LOGGER.error("All LLMs failed to return a valid summary.")
    return None


def summarize_news(url: str, news_text: str, title: str) -> tuple[str, str] | None:
    try:
        if len(news_text) <= 100:
            LOGGER.warning(f"Article text too short ({len(news_text)} chars) for {url}, retrying with cloudscraper.")
            scraper = cloudscraper.create_scraper()
            goose_extractor = Goose({"browser_user_agent": USER_AGENT, "http_session": scraper})
            article = goose_extractor.extract(url=url)

            if not article.cleaned_text or len(article.cleaned_text) <= 100:
                LOGGER.error(f"Cloudscraper also returned insufficient content for {url}.")
                return None

            news_text = article.cleaned_text

        news_text = re.sub(r"\s+", " ", news_text)

        if "businesstimes" in url:
            table_text = extract_table_content(url)
            if table_text:
                news_text = news_text + "\n" + table_text

        LOGGER.info(f"Article content preview: {news_text[:550]}")

        response = summarize_article(title, news_text, url)
        time.sleep(5)

        if not response or not response.get("summary"):
            LOGGER.error(f"Summarization failed or returned incomplete data for {url}.")
            return None

        LOGGER.info(f"Reasoning: {response.get('reasoning')}")
        LOGGER.info(f"Reasoning company name: {response.get('reasoning_company')}")

        raw_body = response.get("summary")
        cleaned_body = basic_cleaning_body(raw_body)
        cleaned_body = clean_apostrophe_case(cleaned_body)
        cleaned_body = normalize_company_abbreviations(cleaned_body)
        cleaned_body = normalize_dot_case(cleaned_body)

        raw_title = response.get("title")
        cleaned_title = normalize_company_abbreviations(raw_title)

        return cleaned_title, cleaned_body

    except Exception as error:
        LOGGER.error(f"Unexpected error in summarize_news for {url}: {error}", exc_info=True)
        return None