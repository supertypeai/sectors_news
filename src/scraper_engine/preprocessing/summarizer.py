from bs4                            import BeautifulSoup
from goose3                         import Goose
from requests                       import Response, Session
from langchain_core.output_parsers  import JsonOutputParser
from langchain.prompts              import ChatPromptTemplate
from io                             import StringIO

from scraper_engine.llm.client  import get_llm, TokenUsageLogger
from scraper_engine.llm.prompts import SummarizationPrompts, SummaryNews
from scraper_engine.config.conf import PROXY, USER_AGENT, HEADERS
from scraper_engine.base.scraper import SeleniumScraper 

import requests
import re
import cloudscraper
import time 
import logging
import csv


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


def summarize_article(body: str, url: str) -> dict[str]:
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
        "article": body,
        'format_instructions': format_instructions
    }
    
    model_names = ['gpt-oss-120b', 'gemini-2.5-flash', 'gpt-oss-20b', 'llama-3.3-70b', 'kimi-k2']
    for model in model_names:
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


def fetch_article_with_proxy(target_url: str) -> str:
    proxy_configuration = {
        "http": PROXY,
        "https": PROXY
    }
    
    headers = {
        "User-Agent": USER_AGENT
    }

    try:
        LOGGER.info(f"Routing {target_url} through proxy")
        
        response = requests.get(
            target_url, 
            proxies=proxy_configuration, 
            headers=headers, 
            verify=False, 
            timeout=60 
        )
        
        if response.status_code == 200:
            LOGGER.info("[SUCCESS] Web Unlocker with proxy")
            return response.text
        
        elif response.status_code == 403:
            LOGGER.error(f"[FAIL] Web Unlocker was blocked (403)")
            return None
        
        else:
            LOGGER.error(f"[FAIL] Target returned status code: {response.status_code}")
            return None
            
    except requests.exceptions.RequestException as network_error:
        LOGGER.error(f"[FAIL] Request through Web Unlocker failed: {network_error}")
        return None


def get_article_bca_news(url: str) -> str:
    headers = {
        "User-Agent": USER_AGENT
    }
    
    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
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


def get_article_bloomberg_technoz_news(url: str) -> str:
    extracted_text_blocks = []
    
    request_headers = {
        "User-Agent": USER_AGENT
    }

    while url:
        try:
            response = requests.get(url, headers=request_headers, timeout=15)
            if response.status_code != 200:
                LOGGER.info(f"[FAIL] Server returned status code: {response.status_code} for URL: {url}")
                break
                
            soup = BeautifulSoup(response.text, "html.parser")
            article_container = soup.find("div", class_="detail-in")
            
            if article_container:
                paragraphs = article_container.find_all("p")
                
                for paragraph in paragraphs:
                    paragraph_text = paragraph.get_text(strip=True)
                    if paragraph_text:
                        extracted_text_blocks.append(paragraph_text)
            else:
                LOGGER.info(f"[FAIL] Could not find the 'detail-in' container on URL: {url}")
                
            # pagination logic: check if a next page exists
            pager_container = soup.find("div", class_="pager")
            if pager_container:
                next_page_element = pager_container.find("a", class_="pager__next")

                if next_page_element and next_page_element.get("href"):
                    url = next_page_element.get("href")
                    continue
                    
            url = None
                
        except requests.RequestException as network_error:
            LOGGER.error(f"[FAIL] Network error occurred: {network_error}")
            break
            
    full_article_text = "\n\n".join(extracted_text_blocks)
    return full_article_text


def get_article_investorid_news(url: str) -> str:
    html_content = fetch_article_with_proxy(url)

    if not html_content:
        LOGGER.info(f"[FAIL INVESTOR.ID] Proxy failed to retrieve HTML for {url}")
        return ""

    soup = BeautifulSoup(html_content, "html.parser")
    
    article_container = soup.select_one("div.body-content")
    
    if not article_container:
        return ""

    paragraphs = article_container.find_all("p")
    extracted_text_blocks = []
    
    for paragraph in paragraphs:
        paragraph_text = paragraph.get_text(strip=True)
        if paragraph_text:
            extracted_text_blocks.append(paragraph_text)
            
    full_article_text = "\n\n".join(extracted_text_blocks)
    return full_article_text


def get_article_kontan_news(url: str) -> str: 
    html_content = fetch_article_with_proxy(url)
    
    if not html_content:
        LOGGER.warning(f"[FAIL INVESTASI KONTAN] Proxy failed to retrieve HTML for {url}")
        return ""
        
    soup = BeautifulSoup(html_content, "html.parser")

    article_container = soup.find('div', class_='tmpt-desk-kon')
    
    if not article_container:
        LOGGER.warning(f"[FAIL] Could not find 'tmpt-desk-kon' container for {url}")
        return ""

    for strong_tag in article_container.find_all('strong'):
        if 'Baca Juga:' in strong_tag.get_text(strip=True):
            parent_paragraph = strong_tag.find_parent('p')
            if parent_paragraph:
                parent_paragraph.decompose()

    paragraphs = article_container.find_all('p')
    extracted_text_blocks = []
    
    for paragraph in paragraphs:
        paragraph_text = paragraph.get_text(strip=True)
      
        if paragraph_text:
            extracted_text_blocks.append(paragraph_text)
            
    full_article_text = "\n\n".join(extracted_text_blocks)
    
    related_news_pattern = r'(?i)berita\s+terkait.*'
    cleaned_article_text = re.sub(related_news_pattern, '', full_article_text, flags=re.DOTALL)
    
    return cleaned_article_text.strip()


def extract_table_content(url: str) -> str:
    headers = {
        "User-Agent": USER_AGENT
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


def extract_via_custom_parser(url: str) -> str | None: 
    try:
        LOGGER.info(f'Attempting custom parser')

        parser = {
            'bcasekuritas.co.id': get_article_bca_news, 
            'bloomberg': get_article_bloomberg_technoz_news, 
            'investor.id': get_article_investorid_news,
            'investasi.kontan': get_article_kontan_news
        }

        for key, parser in parser.items(): 
            if key in url: 
                article = parser(url) 

                if not article: 
                    LOGGER.warning(f'[FAIL CUSTOM PARSER] Failed to extract {url}')
                    return None 
                
                LOGGER.info(f'[SUCCESS] Extracted via custom parser: {url}')
                return article

    except Exception as error:
        LOGGER.error(f"[FAIL] Custom parser failed: {error}")
        return None


def extract_via_cloudscraper(url: str) -> str | None: 
    try:
        LOGGER.info(f"[TIER 1] Attempting fast extraction (No Proxy)")
        scraper_session = cloudscraper.create_scraper() 
        goose_extractor = Goose(
            {'browser_user_agent': USER_AGENT, 'http_session': scraper_session}
        )

        article_data = goose_extractor.extract(url=url)
        
        if article_data and article_data.cleaned_text:
            LOGGER.info(f"[SUCCESS] Extracted via Cloudscraper + Goose: {url}")
            extracted_text = article_data.cleaned_text
            
            if 'www.straitstimes' in url:
                extracted_text = extracted_text.replace("Sign up now: Get ST's newsletters delivered to your inbox", "")
                
            return extracted_text
            
    except Exception as error:
        LOGGER.error(f"[FAIL] Tier 1 Cloudscraper failed: {error}")
        return None 


def extract_via_selenium(url: str) -> str | None: 
    try:
        LOGGER.info(f"[TIER 2] Attempting Selenium extraction (No Proxy)")
        selenium_scraper = SeleniumScraper()
        soup_result = selenium_scraper.fetch_news_with_selenium(url)

        if soup_result:
            raw_html_content = str(soup_result)

            goose_extractor = Goose()
            article_data = goose_extractor.extract(raw_html=raw_html_content)
            
            if article_data and article_data.cleaned_text:
                LOGGER.info(f"[SUCCESS] Extracted via Selenium + Goose: {url}")
                return article_data.cleaned_text
                
            LOGGER.info("[WARNING] Selenium DOM fetched, but Goose failed. Attempting Soup fallbacks.")
            
            content_container = soup_result.find("div", class_="content")
            if content_container and content_container.get_text(strip=True):
                LOGGER.info(f"[SUCCESS] Extracted via Selenium + Soup: {url}")
                return content_container.get_text(strip=True)
            
            antara_container = soup_result.find("div", class_="wrap__article-detail")
            if antara_container and antara_container.get_text(strip=True):
                LOGGER.info(f"[SUCCESS] Extracted via Selenium + Soup: {url}")
                return antara_container.get_text(strip=True)

    except Exception as error:
        LOGGER.error(f"[FAIL] Tier 2 Selenium fallback failed: {error}")    
        return None 


def extract_via_proxy(url: str) -> str | None: 
    try:
        LOGGER.info(f"[TIER 3] Escalating to Proxy")
        
        raw_html_content = fetch_article_with_proxy(url)

        if not raw_html_content:
            LOGGER.warning(f"[FAIL] Proxy network request failed for {url}")
            return None
            
        goose_extractor = Goose()
        article_data = goose_extractor.extract(raw_html=raw_html_content)

        if article_data and article_data.cleaned_text:
            LOGGER.info(f"[SUCCESS] Extracted via Proxy + Goose: {url}")
            return article_data.cleaned_text

    except Exception as error:
        LOGGER.error(f"[FAIL] Tier 3 Proxy extraction failed: {error}")
        return None


def get_article_body(url: str) -> str | None:
    if extracted_text := extract_via_custom_parser(url):
        return extracted_text 

    if extracted_text := extract_via_cloudscraper(url):
        return extracted_text 
 
    if extracted_text := extract_via_selenium(url):
        return extracted_text 

    if extracted_text := extract_via_proxy(url):
        return extracted_text 

    LOGGER.info(f"[FATAL] All extraction tiers failed to retrieve body for: {url}")
    return None


def summarize_news(url: str, news_text: str) -> tuple[str, str] | None:
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

        response = summarize_article(news_text, url)
        time.sleep(5)

        if not response or not response.get("summary"):
            LOGGER.error(f"Summarization failed or returned incomplete data for {url}.")
            return None

        LOGGER.info(f"Reasoning: {response.get('reasoning')}")

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
