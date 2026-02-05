from bs4                            import BeautifulSoup
from nltk.tokenize                  import sent_tokenize, word_tokenize
from goose3                         import Goose
from requests                       import Response, Session
from langchain_core.output_parsers  import JsonOutputParser
from langchain.prompts              import PromptTemplate
from langchain_core.runnables       import RunnableParallel
from operator                       import itemgetter
from groq                           import RateLimitError
from io                             import StringIO

from scraper_engine.llm.client  import LLMCollection, invoke_llm
from scraper_engine.llm.prompts import ClassifierPrompts, SummaryNews
from scraper_engine.config.conf import PROXY

import requests
import re
import nltk
import json 
import cloudscraper
import time 
import random 
import logging
import csv


LOGGER = logging.getLogger(__name__)


# NLTK download
nltk.data.path.append("./nltk_data")


USER_AGENT = "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Mobile Safari/537.36"
HEADERS = {
    "User-Agent": USER_AGENT,
    "Accept": "*/*",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Cache-Control": "max-age=0",
    "x-test": "true",
}

# Model Creation and prompts
LLMCOLLECTION = LLMCollection()
PROMPTS = ClassifierPrompts()


def summarize_article(body: str, url: str) -> dict[str]:
    """ 
    Summarize engine for news articles using LLMs.

    Args:
        body (str): The text of the article to be summarized.
    
    Returns:
        dict[str]: A dictionary containing the title and body of the summary.
    """
    # Get the prompt template for summarization
    template = PROMPTS.get_summarize_prompt()

    # Create a summary parser using the JsonOutputParser
    summary_parser = JsonOutputParser(pydantic_object=SummaryNews)
    
    # Prepare the prompt with the template and format instructions
    summary_prompt = PromptTemplate(
        template=template, 
        input_variables=["article"],
        partial_variables={
            "format_instructions": summary_parser.get_format_instructions()
        }
    )

    # Create a runnable system that will handle the article input
    runnable_summary_system = RunnableParallel(
            {   
                "article": itemgetter("article")
            }
        )

    # Prepare the input data for the LLM
    input_data = {"article": body}
    
    for llm in LLMCOLLECTION.get_llms():
        try:
            llm_used = getattr(llm, 'model_name', getattr(llm, 'model', 'unknown'))
            LOGGER.info(f'LLM used: {llm_used}')
            # Create a summary chain that combines the system, prompt, and LLM
            summary_chain = (
                runnable_summary_system
                | summary_prompt
                | llm 
                | summary_parser
            )
            
            summary_result = invoke_llm(summary_chain, input_data)
            LOGGER.info(f"reason: {summary_result.get('reasoning')}")

            if summary_result is None:
                LOGGER.warning("API call failed after all retries, trying next LLM...")
                continue

            if not summary_result.get("title") or not summary_result.get("summary"):
                LOGGER.info("[ERROR] LLM returned incomplete summary_result")
                continue
            
            LOGGER.info(f"[SUCCES] Summarize for url: {url}")
            return summary_result

        except RateLimitError as error:
            error_message = str(error).lower()
            if "tokens per day" in error_message or "tpd" in error_message:
                LOGGER.warning(f"LLM: {llm_used} hit its daily token limit. Moving to next LLM")
                continue 

        except json.JSONDecodeError as error:
            LOGGER.error(f"Failed to parse JSON response: {error}, trying next LLM...")
            continue
            
        except Exception as error:
            LOGGER.warning(f"LLM failed with error: {error}")
            continue 

    LOGGER.error("All LLMs failed to return a valid summary.")
    return None


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


def get_article_bca_news(url: str) -> str:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    
    try:
        r = requests.get(url, headers=headers)
        r.raise_for_status()
        
        soup = BeautifulSoup(r.text, 'html.parser')
        
        title_tag = soup.find('h1')
        title = title_tag.get_text(strip=True) if title_tag else None

        article_container = soup.select_one('div.prose')
        
        if not article_container:
            LOGGER.info(f"Could not find 'div.prose' in {url}")
            return ""

        paragraphs = article_container.find_all('p')
        
        text_parts = []
        for paragraph in paragraphs:
            text = paragraph.get_text(strip=True)
            # Basic noise filter
            if text and text != "@": 
                text_parts.append(text)
                
        body = "\n\n".join(text_parts)
        body = body.replace('IQPlus,', '')

        article = f'{title}\n' + body
        return article 
    
    except Exception as error:
        LOGGER.error(f"[ERROR] Failed to extract {url}: {error}")
        return ""


def extract_table_content(url: str) -> str:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }
    res = requests.get(url, headers=headers)
    res.raise_for_status()

    soup = BeautifulSoup(res.text, "html.parser")
     
    content_buffer = []
    
    # Find all Datawrapper iframes
    iframes = soup.find_all('iframe', src=lambda x: x and 'datawrapper.dwcdn.net' in x)
    
    for iframe in iframes:
        src = iframe['src']
      
        if src.startswith('//'):
            src = 'https:' + src
            
        try:
            # Datawrapper often exposes data at /dataset.csv
            # Example: https://datawrapper.dwcdn.net/ZslC8/3/ -> https://datawrapper.dwcdn.net/ZslC8/3/dataset.csv
            if src.endswith('/'):
                csv_url = src + 'dataset.csv'
            else:
                csv_url = src + '/dataset.csv'
                
            response = requests.get(csv_url, timeout=5)
            
            if response.status_code == 200:
                csv_text = response.text
                reader = csv.reader(StringIO(csv_text))
                
                # Format as plain text for llm input
                formatted_table = "\nDetail each company in a table form:\n"
                for row in reader:
                    formatted_table += " | ".join(row) + "\n"
                
                content_buffer.append(formatted_table)
                continue 
                
        except Exception:
            pass
            
        # If CSV fails, fetch the iframe HTML and get the title/aria-label
        # (Fallback for when dataset.csv is disabled)
        try:
            response = requests.get(src, timeout=5)
            if response.status_code == 200:
                iframe_soup = BeautifulSoup(response.text, 'html.parser')
                
                # Datawrapper usually puts the title in the <title> tag
                title = iframe_soup.title.string if iframe_soup.title else ""
                content_buffer.append(f"\n[Chart/Table: {title}] (Data extraction failed, view at {src})\n")
                
        except Exception as error:
            LOGGER.info(f"Failed to expand Datawrapper: {error}")
            return ''

    return "\n".join(content_buffer)


def get_article_body(url: str) -> str | None:
    """ 
    Extracts the body of an article from a given URL using Goose3.

    Args:
        url (str): The URL of the article to be extracted.
    
    Returns:
        str: The cleaned text of the article body. If extraction fails, returns an empty string
    """
    if 'bcasekuritas.co.id' in url: 
        article =  get_article_bca_news(url) 
        
        if not article or len(article) < 100:
            return None 
        
        return article 
    
    # First attempt try to get full article with goose3 proxy and soup as fallback
    try:
        proxy = PROXY
        proxy_support = {"http": proxy, "https": proxy}

        session = Session()
        session.proxies.update(proxy_support)
        session.headers.update(HEADERS)
        
        # g = Goose({'http_proxies': proxy_support, 'https_proxies': proxy_support})
        goose_extractor = Goose({"http_session": session})
        article = goose_extractor.extract(url=url)
        LOGGER.info(f"[SUCCESS] Article from url {url} inferenced")

        if article.cleaned_text:
            if 'www.straitstimes' in url:
                texts = article.cleaned_text
                texts = texts.replace("Sign up now: Get ST's newsletters delivered to your inbox", "")
                return texts     
            return article.cleaned_text
        
        else:
            # If fail, get the HTML and extract the text
            LOGGER.info("[REQUEST FAIL] Goose3 returned empty string, trying with soup")
            response: Response = requests.get(url)
            response.raise_for_status()

            soup: BeautifulSoup = BeautifulSoup(response.content, "html.parser")

            content = soup.find("div", class_="content")
            if content and content.get_text(strip=True):
                LOGGER.info(f"[SUCCESS] Article inferenced from url {url} using soup")
                return content.get_text(strip=True)
            
            # Fallback specific for antara news 
            content = soup.find("div", class_="wrap__article-detail")
            if content and content.get_text(strip=True):
                LOGGER.info(f"[SUCCESS] Article inferenced from url {url} using soup class (wrap__article-detail-content)")
                return content.get_text(strip=True)
            
            # Fallback specific for investasi kontan news 
            content = soup.find('div', class_='tmpt-desk-kon')
            if content:
                LOGGER.info(f"[SUCCESS] Article inferenced from url using soup class (tmpt-desk-kon)")
                pattern = r'(?i)berita\s+terkait.*'

                for strong_tag in content.find_all('strong'):
                    if 'Baca Juga:' in strong_tag.get_text():
                        p_tag = strong_tag.find_parent('p')
                        if p_tag:
                            p_tag.decompose()

                text_content = content.get_text(strip=True)
                cleaned_content = re.sub(pattern, '', text_content, flags=re.DOTALL)
                return cleaned_content.strip()
        
    except Exception as error:
        LOGGER.error(
            f"[PROXY FAIL] Goose3 failed with error {error} for url {url}"
        )

    # Fallback two if first attempt is completly failed
    try:
        LOGGER.info("[FALLBACK] Attempt 2: Trying with cloudscraper...")

        scraper = cloudscraper.create_scraper() 
        g = Goose({'browser_user_agent': USER_AGENT, 'http_session': scraper})

        article = g.extract(url=url)
        if article.cleaned_text:
            LOGGER.info(f"[SUCCESS] Extracted using cloudscraper for url {url}.")

            return article.cleaned_text
        
    except Exception as error:
        LOGGER.error(f"[ERROR] Cloudscraper failed: {error}")

    # Last fallback if first and second are failed
    try:
        LOGGER.info("[FALLBACK] Attempt 3: Trying with no PROXY...")

        g = Goose()
        article = g.extract(url=url)

        LOGGER.info(f"[SUCCESS] Article inferenced from url {url} with no PROXY")
        return article.cleaned_text
    
    except Exception as error:
        LOGGER.error(f"[ERROR] Goose3 with no PROXY failed with error: {error}")
    
    return None 


def summarize_news(url: str) -> tuple[str, str]:
    """ 
    Main function to summarize a news article from a given URL.

    Args:
        url (str): The URL of the news article to be summarized.
    
    Returns:
        tuple[str, str]: A tuple containing the title and body of the summarized article.
    """
    try:
        # Getting full article from the url
        news_text = get_article_body(url) or ''
        time.sleep(random.uniform(5, 12))

        if len(news_text) > 100:
            # Preprocess texts by just removing extra spaces
            news_text = re.sub(r"\s+", " ", news_text)
            if 'businesstimes' in url: 
                table_text = extract_table_content(url) 
                if table_text: 
                    news_text = news_text + '\n' + table_text

            LOGGER.info(f"Check full article content: {news_text[:550]}")

            # Summarize the article and force to sleep 5s
            response = summarize_article(news_text, url)
            LOGGER.info(f'reason summary: {response['reasoning']}')
            
            time.sleep(7)

            if not response or not response.get("summary"):
                LOGGER.error(f"Summarization LLM call failed or returned incomplete data for {url}.")
                return None
            
            raw_body = response.get("summary") 
            cleaned_body = basic_cleaning_body(raw_body)
            cleaned_body = clean_apostrophe_case(cleaned_body)
            cleaned_body = normalize_company_abbreviations(cleaned_body)
            cleaned_body = normalize_dot_case(cleaned_body)

            raw_title = response.get("title")
            cleaned_title = normalize_company_abbreviations(raw_title)

            return cleaned_title, cleaned_body
        
        else:
            LOGGER.warning(f"Scraper returned empty content for {url}. Trying with CloudScrapper.")
            scraper = cloudscraper.create_scraper() 
            g = Goose({'browser_user_agent': USER_AGENT, 'http_session': scraper})

            article = g.extract(url=url)
            if article.cleaned_text and len(article.cleaned_text) > 100:
                LOGGER.info(f"[SUCCESS] Extracted using cloudscraper for url {url}.")
                news_text = article.cleaned_text

                news_text = re.sub(r"\s+", " ", news_text)
                if 'businesstimes' in url: 
                    table_text = extract_table_content(url) 
                    if table_text: 
                        news_text = news_text + '\n' + table_text

                LOGGER.info(f"Check full article content: {news_text[:550]}")

                # Summarize the article and force to sleep 5s
                response = summarize_article(news_text, url)
                LOGGER.info(f'reason summary: {response['reasoning']}')

                time.sleep(7)

                if not response or not response.get("summary"):
                    LOGGER.error(f"Summarization LLM call failed or returned incomplete data for {url}.")
                    return None
                
                raw_body = response.get("summary") 
                cleaned_body = basic_cleaning_body(raw_body)
                cleaned_body = clean_apostrophe_case(cleaned_body)
                cleaned_body = normalize_company_abbreviations(cleaned_body)
                cleaned_body = normalize_dot_case(cleaned_body)

                raw_title = response.get("title")
                cleaned_title = normalize_company_abbreviations(raw_title)

                return cleaned_title, cleaned_body
            else:
                LOGGER.error(f"Cloudscraper also returned empty content for {url} or length text < 100.")
                return None

    except Exception as error: 
        LOGGER.error(f"An unexpected error occurred in summarize_news for {url}: {error}", exc_info=True)
        return None

