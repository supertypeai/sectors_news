"""
Script to generate the score of news articles.

Provides comprehensive scoring based on multiple criteria including:
- Timeliness and source credibility
- Clarity, structure, and relevance to Indonesia Stock Market
- Depth of analysis and financial data inclusion
- Market impact and forward-looking statements
- Bonus criteria for high-quality news
"""

from langchain_core.runnables       import RunnableParallel
from operator                       import itemgetter
from langchain.prompts              import PromptTemplate
from langchain_core.output_parsers  import JsonOutputParser
from groq                           import RateLimitError

from llm_models.get_models  import LLMCollection, invoke_llm
from llm_models.llm_prompts import ScoringNews, ClassifierPrompts
from config.setup           import LOGGER

from datetime       import datetime, timedelta
from typing         import Optional
from urllib.parse   import urlparse
import json 
import time
import re 

class ArticleScorer:
    """
    Enhanced article scorer with robust error handling and configurable criteria.
    """
    def __init__(self):
        """
        Initialize the article scorer.
        """
        self.llm_collection = LLMCollection()
        self._criteria_cache: Optional[str] = None

        # Classifier prompts
        self.prompts = ClassifierPrompts()

    def _get_default_criteria(self) -> str:
        """
        Get default scoring criteria.

        Returns:
            str: Default scoring criteria for news articles.
        """
        return """
            News Article Scoring Criteria (0-100). But with bonus point can goes up to 135.

            Tier 0: Noise / Irrelevant (Score 0-10)
            - Description: The news has no discernible connection to the Indonesian market, specific IDX companies, or relevant economic factors. 
              It is generic, trivial, or completely off-topic.
            - Example: "A foreign celebrity launched a new clothing line. The event was attended by many fans."

            Tier 1: General Context (Score 11-40)
            - Description: The news provides general background information about the Indonesian economy, a broad market sector, or global trends that have a weak or indirect link to the IDX. 
              It lacks specific company details or actionable events.
            - Example: "The Indonesian central bank noted that inflation has remained stable for the past quarter. Global commodity prices have seen slight fluctuations this week."

            Tier 2: Notable Event (Score 41-70)
            - Description: The news reports on a specific IDX-listed company or a direct policy change affecting a specific sector. 
              It describes a concrete event like a new project, a strategic partnership, management changes, or an analyst's rating update. 
              This tier is for news that is clearly relevant and noteworthy for tracking.
            - Example: "PT Aneka Tambang (ANTM) announced it is exploring a new partnership to develop an EV battery ecosystem. The company's stock rose 2% on the news."

            Tier 3: Critical & Actionable (Score 71-100)
            - Description: The news reports on a major, market-moving event for a specific IDX-listed company. These are high-impact events that investors often act on immediately.
            - Keywords to look for:
                - Merger / Acquisition (M&A)
                - Earnings Report (especially with results like "beat expectations" or "missed targets")
                - Dividend Announcement (especially with specific rates or dates)
                - Stock Buyback / Rights Issue
                - Major Insider Trading (large buy/sell by executives)
                - A government contract awarded or a major regulatory approval/rejection.
            - Example: "PT GoTo Gojek Tokopedia (GOTO) reported a 30% revenue jump in its Q2 2025 earnings, significantly beating forecasts. The company also announced a 1 trillion rupiah stock buyback program to boost shareholder value."

            Bonus Criteria for High-Quality News (Additional Points)

            1. Primary CTA (Up to 5 Points Each):
                Does the article mention any of the following?
                 - Dividend rate + cum date (+5 points)
                 - Policy/Bill Passing (especially if it's eyeball-catching) (+5 points)
                 - Insider trading (especially if it's eyeball-catching) (+5 points)
                 - Acquisition/Merging (+5 points)
                 - Launching of a new company business plan (new project/income source/new partner/new contract) (+5 points)
                 - Earnings Report (+5 points)

            2. Secondary CTA (Up to 2 Points Each):
                Does the article mention any of the following?
                 - IDX performance against the US market (+2 points)
                 - Rupiah performance (+2 points)
                 - Net foreign buy and sell (+2 points)
                 - Recommended stocks (stock watchlist) (+2 points)
                 - Global commodities prices (+2 points)
                        
            A high quality news article is one that is:
                1. actionable
                2. commercially valuable (request for proposal on a new coal site)
                3. big movement of money (merger and acquisitions, large insider purchase etc)
                4. potential big changes for market cap in the industry
            """
    
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

    def manual_score_source(self, source: str) -> int: 
        """
        Scores a source's credibility based on its domain.

        Args:
            source_url: The full URL of the article source.

        Returns:
            An integer score from 0 to 10.
        """
        extract_domain = self._extract_domain_urlparse(source)
        domain = extract_domain.lower().strip()
        
        top_tier_sources = {"bloomberg.com", "reuters.com", "idx.co.id", "ojk.go.id"}
        national_sources = {"kontan.co.id", "bisnis.com", "cnbcindonesia.com", "investor.id", "kompas.com", "detik.com"}

        # Score 5: Top-tier, highly credible source
        if any(keyword in domain for keyword in top_tier_sources):
            return 5

        # Score 3: Well-established national news outlet
        elif any(keyword in domain for keyword in national_sources):
            return 3 

        # Score 2: Unknown or unreliable source
        else:
            return 1

    def get_article_score(self, body: str, article_date: str, article_source: str) -> int:
        """
        Calculate the score for a news article based on comprehensive criteria.

        Args:
            body (str): The article content to score
            article_date (str): The date of the article in ISO format (YYYY-MM-DD).
            article_source (str): The source url of an article

        Returns:
            int: Score between 0 and 100 (or higher with bonus points)
        """
        # Validation body before goes into llm
        if not body or len(body.strip()) < 10:
            LOGGER.warning(f"Article body is empty or too short for scoring. Returning 0.")
            return 0

        # Get the scoring prompt template
        template = self.prompts.get_scoring_prompt()
        
        # Create a scoring parser using the JsonOutputParser
        scoring_parser = JsonOutputParser(pydantic_object=ScoringNews)

        # Prepare the scoring prompt with the template and format instructions
        scoring_prompt = PromptTemplate(
            template = template, 
            input_variables=[
                "criteria",
                "body",
            ],
            partial_variables={
                "format_instructions": scoring_parser.get_format_instructions()
            }
        )
        scoring_prompt = scoring_prompt.partial(criteria=self._get_default_criteria())

        # Prepare the scoring system that will handle the article input
        runnable_scoring_system = RunnableParallel(
            {   
                "body": itemgetter("body"),
            }
        )

        # Prepare the input data for the LLM
        input_data = {"body":body}

        for llm in self.llm_collection.get_llms():
            try:
                LOGGER.info(f'LLM used: {llm.model}')
                # Create a scoring chain that combines the system, prompt, and LLM
                scoring_chain = (
                        runnable_scoring_system
                        | scoring_prompt
                        | llm
                        | scoring_parser
                    )
                
                # Process with current LLM
                result_score_raw = invoke_llm(scoring_chain, input_data)

                # If the wrapper signaled a permanent API failure, just try the next LLM.
                if result_score_raw is None:
                    LOGGER.warning("API call failed after all retries, trying next LLM...")
                    continue
                
                # Final score adding with manual score time and source
                score_timeliness = self.manual_score_time(article_date)
                score_source_credibilty = self.manual_score_source(article_source)
                result_score = result_score_raw.get('score', 0)
                final_score = result_score + score_source_credibilty + score_timeliness

                if 0 <= final_score <= 155:
                    return final_score
                else: 
                    LOGGER.warning(
                        f"Score out of range: {final_score}, capping at valid range"
                    )
                    return max(0, min(155, final_score))

            except RateLimitError as error:
                error_message = str(error).lower()
                if "tokens per day" in error_message or "tpd" in error_message:
                    LOGGER.warning(f"LLM: {llm.model_name} hit its daily token limit. Moving to next LLM.")
                    continue 

            except json.JSONDecodeError as error:
                LOGGER.error(f"Failed to parse JSON response: {error}")
                continue

            except Exception as error:
                LOGGER.warning(f"LLM failed with error: {error}")
                continue

        LOGGER.error("All llm failed return None for scoring")
        return None 
    

# So we can use the scorer as a singleton
_SCORER = ArticleScorer()

# Backward compatible function
def get_article_score(body: str, article_date: str, article_source: str) -> int:
    """
    Calculate the score for a news article.
    This function maintains backward compatibility with existing code.

    Args:
        body (str): The article content to score

    Returns:
        int: Score between 0 and 100 (or higher with bonus points)
    """
    final_score = _SCORER.get_article_score(body, article_date, article_source)
    LOGGER.info(f'[SUCCES] Scoring news for url: {article_source}')
    time.sleep(7)
    return final_score