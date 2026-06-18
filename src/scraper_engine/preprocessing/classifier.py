from langchain.prompts              import PromptTemplate
from langchain_core.output_parsers  import JsonOutputParser
from langchain_core.runnables       import RunnableParallel
from operator                       import itemgetter
from supabase                       import Client
from datetime                       import datetime
from typing                         import List, Dict, Optional, Union
from pathlib                        import Path
from langchain.prompts              import ChatPromptTemplate

from scraper_engine.llm.client      import get_llm
from scraper_engine.llm.prompts     import (
    ClassifierPrompts, 
    TagsClassification, 
    SubsectorClassification, 
    SentimentClassification, 
    DimensionClassification, 
)
from scraper_engine.config.conf     import MODEL_NAMES
from scraper_engine.database.client import SUPABASE_CLIENT

import json
import logging 
import time 
import re 


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

    def convert_to_kebab(self, sub_sector: str, is_idx: bool = True) -> str:
        if is_idx: 
            return (
                sub_sector
                .replace("&", "")
                .replace(",", "")
                .replace("  ", " ")
                .replace(" ", "-")
                .lower()
            )
        
        result = (
            sub_sector
            .replace("&", "")
            .replace(",", "")
            .replace("  ", " ")
            .replace(" ", "-")
            .lower()
        )

        return re.sub(r'-+', '-', result)

    def _extract_first_sentences(self, text: str, count: int = 2) -> str:
        parts = text.split('.')

        if len(parts) <= count:
            return text.strip()
        
        extracted = parts[:count]
        result = '. '.join(extracted) + '.'
        return result 

    def _load_subsector_data_idx(self) -> str:
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

    def _load_subsector_data_sgx(self) -> tuple: 
        with open("./data/sgx/subsectors_data_sgx.json", "r") as file:
            subsectors = json.load(file) 

        return subsectors

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

    def _load_company_data_idx(self) -> Dict[str, Dict[str, str]]:
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
                    "sub_sector": self.convert_sub_sector_to_kebab(
                        subsector_data[row["sub_sector_id"]], 
                        True
                    ),
                }

            with open("./data/idx/companies.json", "w") as file:
                json.dump(company, file, indent=2)

        else:
            with open("./data/idx/companies.json", "r") as f:
                company = json.load(f)

        self._company_cache = company
        return company
    
    def _load_company_data_sgx(self) -> dict[str, dict[str, str]]:
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
                .eq('is_suspended', False)
                .eq('is_active', True)
                .execute()
            )

            company = {
                item["symbol"]: {
                    "symbol": item["symbol"],
                    "name": item["name"],
                    "sub_sector": self.convert_to_kebab(
                        item["sub_sector"], False
                    ),
                    "sector": self.convert_to_kebab(
                        item["sector"], False
                    )
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
        title: str
    ) -> Optional[Union[list[str], str, dict[str, Optional[int]]]]:
        prompt_methods = {
            "tags": {
                'system_prompt': self.prompts.get_system_tags_prompt(),
                'user_prompt': self.prompts.get_user_tags_prompt()
            },
            "subsectors": {
                'system_prompt': self.prompts.get_system_subsectors_prompt(),
                'user_prompt': self.prompts.get_user_subsectors_prompt()
            },
            "sentiment": {
                'system_prompt': self.prompts.get_sentiment_system_prompt(market=source_scraper),
                'user_prompt': self.prompts.get_sentiment_user_prompt()
            },
            "dimension": {
                'system_prompt': self.prompts.get_system_dimension_prompt(),
                'user_prompt': self.prompts.get_user_dimension_prompt()
            }
        }

        # Load tag data
        tags, tags_string = self._load_tag_data()
        
        # Load subsector data
        if source_scraper == 'sgx': 
            subsectors = self._load_subsector_data_sgx() 

        elif source_scraper == 'idx':
            subsectors, _ = self._load_subsector_data_idx()

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
        system_prompt = prompt_methods[category]['system_prompt']
        user_prompt = prompt_methods[category]['user_prompt']
      
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ('user', user_prompt)
        ])
        
        format_instructions = classifier_parser.get_format_instructions()
        
        if category == "tags":
            input_data = {
                "title": title, 
                "body": body, 
                "tags": tags_string, 
                "format_instructions": format_instructions
            }
        
        elif category == "subsectors":
            input_data = {
                "title": title, 
                "body": body, 
                "subsectors": subsectors, 
                "format_instructions": format_instructions
            }
        
        else:
            input_data = {
                "title": title, 
                "body": body, 
                "format_instructions": format_instructions
            }

        for model in MODEL_NAMES:
            try:
                llm = get_llm(model, temperature=0.4)
                LOGGER.info(f'LLM used: {model}')

                classifier_chain = prompt | llm | classifier_parser

                result = classifier_chain.invoke(input_data)

                time.sleep(8)

                if result is None : 
                    LOGGER.warning(f"API call failed for category: {category}. trying next LLM.")
                    continue 

                # Return based on category type             
                if category == "tags":                      
                    result_output = result.get("tags", [])
                    reason = result.get('reason')

                    LOGGER.info('reason tags: %s', reason)

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
                    reasoning = result.get('reasoning')

                    if len(sub_sector) >= 10:
                        continue 
                    
                    LOGGER.info('Reasoning subsector: %s', reasoning)

                    return sub_sector
                
                elif category == "sentiment":
                    LOGGER.info('Reason sentiment: %s', result.get('reasoning'))
                    return result.get("sentiment", "Not Applicable")
                
                elif category == "dimension":
                    result.pop("reasoning", None)

                    if isinstance(result, dict):
                        return result

            except Exception as error:
                LOGGER.error(f"[ERROR] LLM failed classified with error: {error}", exc_info=True)
                continue
            
        LOGGER.error(f"All LLMs failed for category '{category}'.")
        return None

    def classify_article(
        self, 
        title: str, 
        body: str, 
        source_scraper: str
    ) -> tuple[list[str], str, dict[str, Optional[int]]]:
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
    return CLASSIFIER._load_company_data_idx()


def load_company_data_sgx() -> Dict[str, Dict[str, str]]:
    """
    Load company data sgx from Supabase or cache.

    Returns:
        Dict[str, Dict[str, str]]: Dictionary mapping company symbols to their details.
    """
    return CLASSIFIER._load_company_data_sgx()


def load_sub_sectors_data() -> dict[str]:
    """
    Load subsector data from json.

    Returns:
        dict[str]: Dictionary containing subsector data.
    """
    _, keys = CLASSIFIER._load_subsector_data_idx()
    return keys


def load_sub_sectors_data_sgx() -> dict[str]:
    """
    Load subsector data sgx from json.

    Returns:
        dict[str]: Dictionary containing subsector data.
    """
    sub_sectors = CLASSIFIER._load_subsector_data_sgx()
    return sub_sectors