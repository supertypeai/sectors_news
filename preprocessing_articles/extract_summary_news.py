"""
Script to use LLM for summarizing a news article, uses Llama Groq
"""

from bs4                            import BeautifulSoup
from nltk.tokenize                  import sent_tokenize, word_tokenize
from goose3                         import Goose
from requests                       import Response, Session
from langchain_core.output_parsers  import JsonOutputParser
from langchain.prompts              import PromptTemplate
from langchain_core.runnables       import RunnableParallel
from operator                       import itemgetter
from groq                           import RateLimitError

from llm_models.get_models  import LLMCollection, invoke_llm
from llm_models.llm_prompts import ClassifierPrompts, SummaryNews
from config.setup           import LOGGER

import requests
import os
import re
import nltk
import json 
import cloudscraper
import time 
import random 

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
            # Create a summary chain that combines the system, prompt, and LLM
            summary_chain = (
                runnable_summary_system
                | summary_prompt
                | llm 
                | summary_parser
            )
            
            summary_result = invoke_llm(summary_chain, input_data)
            if summary_result is None:
                LOGGER.warning("API call failed after all retries, trying next LLM...")
                continue

            if not summary_result.get("title") or not summary_result.get("body"):
                LOGGER.info("[ERROR] LLM returned incomplete summary_result")
                continue
            
            LOGGER.info(f"[SUCCES] Summarize for url: {url}")
            return summary_result

        except RateLimitError as error:
            error_message = str(error).lower()
            if "tokens per day" in error_message or "tpd" in error_message:
                LOGGER.warning(f"LLM: {llm.model_name} hit its daily token limit. Moving to next LLM")
                continue 

        except json.JSONDecodeError as error:
            LOGGER.error(f"Failed to parse JSON response: {error}, trying next LLM...")
            continue
            
        except Exception as error:
            LOGGER.warning(f"LLM failed with error: {error}")
            continue 

    LOGGER.error("All LLMs failed to return a valid summary.")
    return None


def preprocess_text(news_text: str) -> str:
    """ 
    Preprocesses the news text by removing parenthesis, tokenizing sentences and words,
    removing stopwords, and formatting the text.

    Args:
        news_text (str): The raw text of the news article to be preprocessed.

    Returns:
        str: The preprocessed text ready for summarization.
    """
    # Remove parenthesis
    news_text = re.sub(r"\(.*?\)", "", news_text)

    # Tokenize into sentences
    sentences = sent_tokenize(news_text)

    # Tokenize into words, remove stopwords, and convert to lowercase
    stop_words = {
        "a",
        "an",
        "the",
        "with",
        "of",
        "to",
        "and",
        "in",
        "on",
        "for",
        "as",
        "by",
    }
    words = [word_tokenize(sentence) for sentence in sentences]
    words = [
        [word.lower() for word in sentence if word.lower() not in stop_words]
        for sentence in words
    ]

    # Combine words back into sentences
    processed_sentences = [" ".join(sentence) for sentence in words]

    # Combine sentences back into a single string
    processed_text = " ".join(processed_sentences)

    # Remove spaces before punctuation
    processed_text = re.sub(r'\s+([?.!,"])', r"\1", processed_text)
    # Remove multiple spaces
    processed_text = re.sub(r"\s+", " ", processed_text)

    return processed_text


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


def get_article_body(url: str) -> str:
    """ 
    Extracts the body of an article from a given URL using Goose3.

    Args:
        url (str): The URL of the article to be extracted.
    
    Returns:
        str: The cleaned text of the article body. If extraction fails, returns an empty string
    """
    # First attempt try to get full article with goose3 proxy and soup as fallback
    try:
        proxy = os.environ.get("PROXY")
        proxy_support = {"http": proxy, "https": proxy}

        session = Session()
        session.proxies.update(proxy_support)
        session.headers.update(HEADERS)

        # g = Goose({'http_proxies': proxy_support, 'https_proxies': proxy_support})
        g = Goose({"http_session": session})
        article = g.extract(url=url)
        print(f"[SUCCESS] Article from url {url} inferenced")

        if article.cleaned_text:
            return article.cleaned_text
        else:
            # If fail, get the HTML and extract the text
            print("[REQUEST FAIL] Goose3 returned empty string, trying with soup")
            response: Response = requests.get(url)
            response.raise_for_status()

            soup: BeautifulSoup = BeautifulSoup(response.content, "html.parser")

            content = soup.find("div", class_="content")
            if content and content.get_text(strip=True):
                print(f"[SUCCESS] Article inferenced from url {url} using soup")
                return content.get_text(strip=True)
            
            # Fallback specific for antara news 
            content = soup.find("div", class_="wrap__article-detail")
            if content and content.get_text(strip=True):
                print(f"[SUCCESS] Article inferenced from url {url} using soup class (wrap__article-detail-content)")
                return content.get_text(strip=True)
            
            # Fallback specific for investasi kontan news 
            content = soup.find('div', class_='tmpt-desk-kon')
            if content:
                print(f"[SUCCESS] Article inferenced from url using soup class (tmpt-desk-kon)")
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
        print(
            f"[PROXY FAIL] Goose3 failed with error {error} for url {url}"
        )

    # Fallback two if first attempt is completly failed
    try:
        print("[FALLBACK] Attempt 2: Trying with cloudscraper...")

        scraper = cloudscraper.create_scraper() 
        g = Goose({'browser_user_agent': USER_AGENT, 'http_session': scraper})

        article = g.extract(url=url)
        if article.cleaned_text:
            print(f"[SUCCESS] Extracted using cloudscraper for url {url}.")

            return article.cleaned_text
        
    except Exception as error:
        print(f"[ERROR] Cloudscraper failed: {error}")

    # Last fallback if first and second are failed
    try:
        print("[FALLBACK] Attempt 3: Trying with no PROXY...")

        g = Goose()
        article = g.extract(url=url)

        print(f"[SUCCESS] Article inferenced from url {url} with no PROXY")
        return article.cleaned_text
    
    except Exception as error:
        print(f"[ERROR] Goose3 with no PROXY failed with error: {error}")
    
    return ""


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
        news_text = get_article_body(url)
        time.sleep(random.uniform(5, 12))
        LOGGER.info(f"Check full article content: {news_text[:550]}")
        
        if len(news_text) > 0:
            news_text = preprocess_text(news_text)

            # Summarize the article and force to sleep 5s
            response = summarize_article(news_text, url)
            time.sleep(5)

            if not response or not response.get("body"):
                LOGGER.error(f"Summarization LLM call failed or returned incomplete data for {url}.")
                return None
            
            raw_body = response.get("body") 
            cleaned_body = basic_cleaning_body(raw_body)

            return response.get("title"), cleaned_body
        else:
            LOGGER.warning(f"Scraper returned empty content for {url}. Trying with CloudScrapper.")
            scraper = cloudscraper.create_scraper() 
            g = Goose({'browser_user_agent': USER_AGENT, 'http_session': scraper})

            article = g.extract(url=url)
            if article.cleaned_text:
                print(f"[SUCCESS] Extracted using cloudscraper for url {url}.")
                news_text = article.cleaned_text
                news_text = preprocess_text(news_text)

                # Summarize the article and force to sleep 5s
                response = summarize_article(news_text, url)
                time.sleep(5)

                if not response or not response.get("body"):
                    LOGGER.error(f"Summarization LLM call failed or returned incomplete data for {url}.")
                    return None
                
                return response.get("title"), response.get("body")
            else:
                LOGGER.error(f"Cloudscraper also returned empty content for {url}.")
                return None

    except Exception as error: 
        LOGGER.error(f"An unexpected error occurred in summarize_news for {url}: {error}")
        return None


# urls = [
#     "https://www.idnfinancials.com/news/50366/boosting-growth-tpma-acquires-worth-us",
#     "https://www.idnfinancials.com/news/50438/consistent-profit-dividend-ptba-rakes-indeks-categories",
#     "https://www.idnfinancials.com/news/50433/smdr-listed-dividend-category-indeks-tempo-idnfinancials",
#     "https://www.idnfinancials.com/news/50431/declining-market-cap-sido-listed-categories-indeks"
# ]

# for url in urls:
#     title, body = summarize_news(url)
#     print(title)
#     print(body)