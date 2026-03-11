from langchain.prompts              import PromptTemplate
from langchain_core.output_parsers  import JsonOutputParser
from langchain_core.runnables       import RunnableParallel
from operator                       import itemgetter
from supabase                       import Client
from datetime                       import datetime
from typing                         import List, Dict, Optional, Union, Tuple
from groq                           import RateLimitError
from pathlib                        import Path

from scraper_engine.llm.client  import invoke_llm, get_llm
from scraper_engine.llm.prompts import (
    ClassifierPrompts, 
    TagsClassification, 
    TickersClassification, 
    SubsectorClassification, 
    SentimentClassification, 
    DimensionClassification, 
    CompanyNameTickerExtraction,
    CompanyNameExtraction
)

from scraper_engine.database.client import SUPABASE_CLIENT

import json
import asyncio
import logging 
import time 


LOGGER = logging.getLogger(__name__)


class NewsClassifier:
    """
    A class to handle news article classification including tags, subsectors, tickers, and sentiment.
    """
    def __init__(self):
        self.supabase: Client = SUPABASE_CLIENT

        self._subsectors_cache: Optional[Dict[str, str]] = None
        self._tags_cache: Optional[List[str]] = None
        self._company_cache: Optional[Dict[str, Dict[str, str]]] = None
        self._prompts_cache: Optional[Dict] = None

        self._company_cache_sgx: Optional[Dict[str, Dict[str, str]]] = None
        self._sgx_cache_refreshed_on: Optional[str] = None

        self.prompts = ClassifierPrompts()

    def _extract_first_sentences(self, text: str, count: int = 2) -> str:
        parts = text.split('.')

        if len(parts) <= count:
            return text.strip()
        
        extracted = parts[:count]
        result = '. '.join(extracted) + '.'
        return result 

    def _load_subsector_data(self) -> str:
        if self._subsectors_cache is not None:
            return self._subsectors_cache

        if datetime.today().day in [1, 15]:
            response = (
                self.supabase.table("idx_subsector_metadata")
                .select("slug, description")
                .execute()
            )

            subsectors = {row["slug"]: row["description"] for row in response.data}

            with open("./data/idx/subsectors_data.json", "w") as file:
                json.dump(subsectors, file, indent=2)
        else:
            with open("./data/idx/subsectors_data.json", "r") as file:
                subsectors = json.load(file)

        # Extract only the first two sentences
        subsector_clean = {}
        for key, value in subsectors.items():
            clean_value = self._extract_first_sentences(value)
            subsector_clean[key] = clean_value 
        
        subsector_string = "\n\n".join(
            [
                f"{key}:{value}" for key, value in subsector_clean.items()
            ]
        )

        result = (subsector_string, set(subsectors.keys()))
        self._subsectors_cache = result
        return result

    def _load_subsector_data_sgx(self) -> str: 
        with open("./data/sgx/subsectors_data_sgx.json", "r") as file:
            subsectors = json.load(file) 

        subsector_string = "\n".join(
            [
                f"{key}:{value}" for key, value in subsectors.items()
            ]
        )

        return subsector_string, set(subsectors.keys())

    def _load_tag_data(self) -> tuple:
        """
        Load tag data from JSON file.

        Returns:
            List[str]: List of available tags
        """
        if self._tags_cache is not None:
            return self._tags_cache

        with open("./data/unique_tags.json", "r") as file:
            tags = json.load(file)
            tags = tags.get('tags')
        
        full_tags = '\n\n'.join(
            f"{tag.get('name')} : {tag.get('description')}" for tag in tags
        )
        
        self._tags_cache = (tags, full_tags)
        return tags, full_tags

    def _load_company_data(self) -> Dict[str, Dict[str, str]]:
        """
        Load company data from Supabase or cache.

        Returns:
            Dict[str, Dict[str, str]]: Dictionary mapping company symbols to their details
        """
        if self._company_cache is not None:
            return self._company_cache

        if datetime.today().day in [1, 15]:
            response = (
                self.supabase.table("idx_company_profile")
                .select("symbol, company_name, sub_sector_id")
                .execute()
            )

            subsector_response = (
                self.supabase.table("idx_subsector_metadata")
                .select("sub_sector_id, sub_sector")
                .execute()
            )

            subsector_data = {
                row["sub_sector_id"]: row["sub_sector"]
                for row in subsector_response.data
            }

            company = {}
            for row in response.data:
                company[row["symbol"]] = {
                    "symbol": row["symbol"],
                    "name": row["company_name"],
                    "sub_sector": subsector_data[row["sub_sector_id"]],
                }

            for attr in company:
                company[attr]["sub_sector"] = (
                    company[attr]["sub_sector"]
                    .replace("&", "")
                    .replace(",", "")
                    .replace("  ", " ")
                    .replace(" ", "-")
                    .lower()
                )

            with open("./data/idx/companies.json", "w") as f:
                json.dump(company, f, indent=2)
        else:
            with open("./data/idx/companies.json", "r") as f:
                company = json.load(f)

        self._company_cache = company
        return company
    
    def _load_sgx_company_data(self) -> Dict[str, Dict[str, str]]:
        DATA_DIR = Path("data")
        path = DATA_DIR / "sgx/sgx_companies.json"

        today = datetime.today().strftime("%Y-%m-%d")
        refresh_day = datetime.today().day in {1, 15}

        if self._company_cache_sgx is not None:
            if not refresh_day or self._sgx_cache_refreshed_on == today:
                return self._company_cache_sgx

        if refresh_day:
            response = (
                SUPABASE_CLIENT
                .table("sgx_company_report")
                .select("symbol", "name", "sub_sector", "sector")
                .execute()
            )
            company = {
                item["symbol"]: {
                    "symbol": item["symbol"],
                    "name": item["name"],
                    "sub_sector": item["sub_sector"].lower(),
                    "sector": item["sector"].lower(),
                }
                for item in response.data
            }
            with open(path, "w") as file:
                json.dump(company, file, indent=4)
            self._sgx_cache_refreshed_on = today

        else:
            with open(path, "r") as file:
                company = json.load(file)

        self._company_cache_sgx = company
        return company

    def _classify_data(
        self, 
        body: str, 
        category: str, 
        source_scraper: str, 
        title: str = ""
    ) -> Optional[Union[list[str], str, dict[str, Optional[int]]]]:
        prompt_methods = {
            "tags": self.prompts.get_tags_prompt(),
            "subsectors": self.prompts.get_subsectors_prompt(),
            "sentiment": self.prompts.get_sentiment_prompt(),
            "dimension": self.prompts.get_dimension_prompt()
        }

        # Load tag data
        tags, tags_string = self._load_tag_data()
        
        # Load subsector data
        subsectors, _ = (
            self._load_subsector_data_sgx() if source_scraper == "sgx"
            else self._load_subsector_data()
        )

        # Pydantic mapping 
        model_mapping = {
            "tags": TagsClassification,
            "subsectors": SubsectorClassification,
            "sentiment": SentimentClassification,
            "dimension": DimensionClassification
        }

        # Create Parser
        classifier_parser = JsonOutputParser(pydantic_object=model_mapping.get(category))
        
        # Get prompt template
        template = prompt_methods.get(category)

        # Get input variables based on category
        if category.lower() == 'dimension':
            input_variables = ["title", "body"]
        else:
            input_variables = ['body']

        # Create prompt with input variables and format instructions
        prompt = PromptTemplate(
            template=template, 
            input_variables=input_variables,
            partial_variables={
                "format_instructions": classifier_parser.get_format_instructions()
            }
        )

        # Add category-specific data to prompt
        if category == "tags":
            prompt = prompt.partial(tags=tags_string)

        elif category == "subsectors":
            prompt = prompt.partial(subsectors=subsectors)

        # Create runnable system based on category
        if category == "dimension":
            runnable_system = RunnableParallel({
                "title": itemgetter("title"),
                "body": itemgetter("body")
            })
        else:
            runnable_system = RunnableParallel({
                "body": itemgetter("body")
            })
        
        # Prepare input data
        if category == "dimension":
            input_data = {"title": title, "body": body}
        else:
            input_data = {"body": body}

        model_names = ['gpt-oss-120b', 'gemini-2.5-flash', 'gpt-oss-20b', 'llama-3.3-70b', 'kimi-k2']
        for model in model_names:
            try:
                llm = get_llm(model, temperature=0.4)
                LOGGER.info(f'LLM used: {model}')

                # Create chain with current LLM
                classifier_chain = (
                    runnable_system
                    | prompt 
                    | llm 
                    | classifier_parser
                )

                # Process with current LLM
                result = invoke_llm(classifier_chain, input_data)
    
                # Sleep 8s
                time.sleep(8)

                if result is None : 
                    LOGGER.warning(f"API call failed for category: {category}. trying next LLM.")
                    continue 

                # Return based on category type             
                if category == "tags":                      
                    result_output = result.get("tags", [])  
                    tags = [tag.get('name') for tag in tags]

                    seen = set()
                    check_tags = []
                    for tag in result_output:
                        if tag in tags and tag not in seen:
                            seen.add(tag)
                            check_tags.append(tag) 
                    return check_tags
                
                elif category == "subsectors":
                    sub_sector = result.get("subsector", "")
                    if len(sub_sector) >= 10:
                        continue 
                    return sub_sector
                
                elif category == "sentiment":
                    return result.get("sentiment", "")
                
                elif category == "dimension":
                    if isinstance(result, dict):
                        return result
                    else:
                        # Fallback if result is not a dict
                        return {
                            "valuation": result.get("valuation", None),
                            "future": result.get("future", None),
                            "technical": result.get("technical", None),
                            "financials": result.get("financials", None),
                            "dividend": result.get("dividend", None),
                            "management": result.get("management", None),
                            "ownership": result.get("ownership", None),
                            "sustainability": result.get("sustainability", None),
                        }

            except Exception as error:
                LOGGER.error(f"[ERROR] LLM failed classified with error: {error}")
                continue
            
        LOGGER.error(f"All LLMs failed for category '{category}'.")
        return None

    def classify_article(
        self, title: str, body: str, source_scraper: str
    ) -> Optional[tuple[list[str], str, dict[str, Optional[int]]]]:
        # Llama groq sensitive to ratelimit, so decided to not use .gather but sequential instead
        tags = self._classify_data(body, "tags", source_scraper, title)
        # subsector = self._classify_data_async(body, "subsectors", title)
        sentiment = self._classify_data(body, "sentiment", source_scraper, title)
        dimension = self._classify_data(body, "dimension", source_scraper, title)

        # Check for ANY failure: either an unexpected Exception OR None signal
        results = [tags, sentiment, dimension]
        if any(isinstance(res, Exception) or res is None for res in results):
            LOGGER.error("One or more classification steps failed. Failing entire article classification.")
            return None

        return tags, sentiment, dimension


# Create a singleton instance
CLASSIFIER = NewsClassifier()

# Backward compatibility functions
def load_company_data() -> Dict[str, Dict[str, str]]:
    """
    Load company data from Supabase or cache.

    Returns:
        Dict[str, Dict[str, str]]: Dictionary mapping company symbols to their details.
    """
    return CLASSIFIER._load_company_data()


def load_company_data_sgx() -> Dict[str, Dict[str, str]]:
    """
    Load company data sgx from Supabase or cache.

    Returns:
        Dict[str, Dict[str, str]]: Dictionary mapping company symbols to their details.
    """
    return CLASSIFIER._load_sgx_company_data()


def load_sub_sectors_data() -> dict[str]:
    """
    Load subsector data from json.

    Returns:
        dict[str]: Dictionary containing subsector data.
    """
    _, keys = CLASSIFIER._load_subsector_data()
    return keys


def load_sub_sectors_data_sgx() -> dict[str]:
    """
    Load subsector data sgx from json.

    Returns:
        dict[str]: Dictionary containing subsector data.
    """
    _, keys = CLASSIFIER._load_subsector_data_sgx()
    return keys