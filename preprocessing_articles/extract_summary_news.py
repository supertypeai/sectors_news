"""
Script to use LLM for summarizing a news article, uses OpenAI and Groq
"""

from bs4                            import BeautifulSoup
from nltk.tokenize                  import sent_tokenize, word_tokenize
from goose3                         import Goose
from requests                       import Response, Session
from langchain_core.output_parsers  import JsonOutputParser
from langchain.prompts              import PromptTemplate
from langchain_core.runnables       import RunnableParallel
from operator                       import itemgetter

from llm_models.get_models  import LLMCollection, invoke_llm
from llm_models.llm_prompts import ClassifierPrompts, SummaryNews
from config.setup           import LOGGER

import requests
import os
import re
import nltk
import openai 
import json 

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


def summarize_article(body: str) -> dict[str]:
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
            
            try:
                summary_result = invoke_llm(summary_chain, input_data)
            except json.JSONDecodeError as error:
                error_msg = str(error)
                LOGGER.error("Failed to parse JSON response", error_msg)
                summary_result = json_handle_payload(error_msg)

            if not summary_result.get("title") or not summary_result.get("body"):
                LOGGER.info("[ERROR] LLM returned incomplete summary_result")
                continue

            return summary_result

        except openai.RateLimitError as limit:
                # Re-raise the error of rate limit
                raise limit
            
        except Exception as error:
            LOGGER.warning(f"LLM failed with error: {error}")
    
    return {"title": "", "body": ""}


def json_handle_payload(json_str):
    """
    Cleans and parses a JSON string into a Python dictionary.
    
    Args:
        json_str (str): The JSON string to be cleaned and parsed.

    Returns:
        dict: A Python dictionary representation of the JSON string if parsing is successful.
              If parsing fails, returns a dictionary containing an "error" key with the error message.
    """

    # Pre-process to fix common JSON issues like trailing commas
    response_text = re.sub(r',\s*([\]}])', r'\1', json_str)  # Remove trailing commas before closing braces or brackets
    try:
        # Attempt to parse the JSON
        response = json.loads(response_text)
    except json.JSONDecodeError as error:
        error_message = str(error)
        LOGGER.error(f"Failed to parse JSON response After trying to fix commas: {error_message}")
        response = {"error": error_message}

    return response


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


def get_article_body(url: str) -> str:
    """ 
    Extracts the body of an article from a given URL using Goose3.

    Args:
        url (str): The URL of the article to be extracted.
    
    Returns:
        str: The cleaned text of the article body. If extraction fails, returns an empty string
    """
    try:
        proxy = os.environ.get("PROXY_KEY")
        proxy_support = {"http": proxy, "https": proxy}

        session = Session()
        session.proxies.update(proxy_support)
        session.headers.update(HEADERS)

        # g = Goose({'http_proxies': proxy_support, 'https_proxies': proxy_support})
        g = Goose({"http_session": session})
        article = g.extract(url=url)
        print(f"[SUCCESS] Article from url {url} inferenced")
        # print("cleaned text", article.cleaned_text)

        if article.cleaned_text:
            return article.cleaned_text
        else:
            # If fail, get the HTML and extract the text
            print("[REQUEST FAIL] Goose3 returned empty string, trying with soup")
            response: Response = requests.get(url)
            response.raise_for_status()

            soup: BeautifulSoup = BeautifulSoup(response.content, "html.parser")
            content: BeautifulSoup = soup.find("div", class_="content")
            print(f"[SUCCESS] Article inferenced from url {url} using soup")
            return content.get_text()
        
    except Exception as error:
        print(
            f"[PROXY FAIL] Goose3 failed with error, trying with no proxy: {error} to url {url}"
        )
        try:
            g = Goose()
            article = g.extract(url=url)
            return article.cleaned_text
        except Exception as error:
            print(f"[ERROR] Goose3 failed with error: {error}")
            return ""


def summarize_news(url: str) -> tuple[str, str]:
    """ 
    Main function to summarize a news article from a given URL.

    Args:
        url (str): The URL of the news article to be summarized.
    
    Returns:
        tuple[str, str]: A tuple containing the title and body of the summarized article.
    """
    news_text = get_article_body(url)
    if len(news_text) > 0:
        news_text = preprocess_text(news_text)
        response = summarize_article(news_text)

        return response.get("title"), response.get("body")
    else:
        return "", ""


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