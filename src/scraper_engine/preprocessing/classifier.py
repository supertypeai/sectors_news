from langchain_core.output_parsers import JsonOutputParser
from typing import Optional, Union
from langchain.prompts import ChatPromptTemplate

from scraper_engine.llm.client import get_llm
from scraper_engine.llm.prompts import (
    ClassifierPrompts, 
    TagsClassification, 
    SubsectorClassification, 
    SentimentClassification, 
    DimensionClassification, 
)
from scraper_engine.config.conf import MODEL_NAMES
from scraper_engine.database.metadata import (
    load_subsector_data_idx as load_subsector_data_idx_from_metadata,
    load_subsector_data_sgx as load_subsector_data_sgx_from_metadata,
    load_tag_data as load_tag_data_from_metadata,
)

import logging 
import time 


LOGGER = logging.getLogger(__name__)


class NewsClassifier:
    def __init__(self):
        self.prompts = ClassifierPrompts()

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
        tags, tags_string = load_tag_data_from_metadata()
        
        # Load subsector data
        if source_scraper == 'sgx': 
            subsectors = load_subsector_data_sgx_from_metadata()

        elif source_scraper == 'idx':
            subsectors, _ = load_subsector_data_idx_from_metadata()

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

