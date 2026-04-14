from langchain.prompts              import ChatPromptTemplate
from langchain_core.output_parsers  import JsonOutputParser

from scraper_engine.llm.client  import get_llm
from scraper_engine.llm.prompts import ScoringNews, ScoringPrompts
from scraper_engine.config.conf import MODEL_NAMES

from datetime       import datetime, timedelta
from typing         import Optional
from urllib.parse   import urlparse

import time
import logging


LOGGER = logging.getLogger(__name__)


class ArticleScorer:
    """
    Enhanced article scorer with robust error handling and configurable criteria.
    """
    def __init__(self):
        """
        Initialize the article scorer.
        """
        self._criteria_cache: Optional[str] = None

        # Classifier prompts
        self.prompts = ScoringPrompts()
    
    def _extract_domain_urlparse(self, url:str):
        """
        Extract domain from URL using urllib.parse (more robust)
        
        Args:
            url (str): Input URL
            
        Returns:
            str: Domain name or None if invalid
        """
        try:
            parsed = urlparse(url)
            return parsed.netloc
        except:
            return None

    def manual_score_time(self, publication_timestamp: str) -> int:
        """
        Scores an article's timeliness based on its publication date.

        Args:
            publication_timestamp: A datetime object representing when the article was published.

        Returns:
            An integer score from 0 to 10.
        """
        if isinstance(publication_timestamp, str): 
            publication_timestamp = datetime.strptime(publication_timestamp, '%Y-%m-%d %H:%M:%S')
        
        current_time = datetime.now()

        # scoring manual for timestamp 
        time_difference = current_time - publication_timestamp 

        # Score 5: Very recent (published within the last 48 hours)
        if time_difference <= timedelta(hours=48):
            return 5
    
        # Score 3: Recent (published within the last week)
        elif time_difference <= timedelta(days=7):
            return 3 

        # Score 2: Somewhat recent (published within the last 2 weeks)
        elif time_difference <= timedelta(days=14):
            return 2 

        # Score 1: Outdated (more than 2 weeks old)
        else:
            return 1

    def get_article_score(self, body: str, article_date: str, article_source: str, source_scraper: str) -> int:
        if not body or len(body.strip()) < 10:
            LOGGER.warning(f"Article body is empty or too short for scoring. Returning 0.")
            return 0

        if source_scraper == 'sgx': 
            system_prompt = self.prompts.get_scoring_system_prompt_sgx()
        else: 
            system_prompt = self.prompts.get_scoring_system_prompt_idx()
        
        user_prompt = self.prompts.get_scoring_user_prompt()

        scoring_parser = JsonOutputParser(pydantic_object=ScoringNews)
        format_instructions = scoring_parser.get_format_instructions()

        prompt = ChatPromptTemplate.from_messages([
            ("system", system_prompt),
            ('user', user_prompt )
        ])

        input_data = {
            "article": body, 
            'format_instructions': format_instructions
        }

        for model in MODEL_NAMES:
            try:
                llm = get_llm(model, temperature=0.4)
                LOGGER.info(f"LLM used: {model}")
            
                scoring_chain = prompt | llm | scoring_parser
                
                response = scoring_chain.invoke(input_data)

                if response is None:
                    LOGGER.warning("API call failed after all retries, trying next LLM...")
                    continue
                
                LOGGER.info(f'Reason scoring: {response.get('reason')}')

                score_timeliness = self.manual_score_time(article_date)
                result_score = response.get('score', 0)
                final_score = result_score + score_timeliness

                if 0 <= final_score <= 155:
                    return final_score
                else: 
                    LOGGER.warning(
                        f"Score out of range: {final_score}, capping at valid range"
                    )
                    return max(0, min(155, final_score))

            except Exception as error:
                LOGGER.warning(f"LLM failed with error: {error}")
                continue

        LOGGER.error("All llm failed return None for scoring")
        return None 
    

# Backward compatible function
def get_article_score(body: str, article_date: str, article_source: str, source_criteria: str) -> int:
    """
    Calculate the score for a news article.
    This function maintains backward compatibility with existing code.

    Args:
        body (str): The article content to score

    Returns:
        int: Score between 0 and 100 (or higher with bonus points)
    """
    scorer = ArticleScorer()
    final_score = scorer.get_article_score(body, article_date, article_source, source_criteria)
    LOGGER.info(f'[SUCCES] Scoring news for url: {article_source}')
    time.sleep(7)
    return final_score