from pydantic import Field, BaseModel
from typing   import List, Optional


# Define Pydantic models for each classification type
class ScoringNews(BaseModel):
    score: int = Field(description="Score of article summary")

class SummaryNews(BaseModel):
    title: str = Field(description="Title from an article") 
    body: str = Field(description="Two sentences summary from an article")

class TagsClassification(BaseModel):
    tags: List[str] = Field(description="List of relevant tags for the article")

class TickersClassification(BaseModel):
    tickers: List[str] = Field(description="List of stock tickers mentioned in the article")

class SubsectorClassification(BaseModel):
    subsector: List[str] = Field(description="Primary subsector classification")

class SentimentClassification(BaseModel):
    sentiment: str = Field(description="Sentiment classification (Bullish, Bearish, Neutral)")

class DimensionClassification(BaseModel):
    valuation: Optional[int] = Field(description="Valuation score (0-2)", default=0)
    future: Optional[int] = Field(description="Future prospects score (0-2)", default=0)
    technical: Optional[int] = Field(description="Technical analysis score (0-2)", default=0)
    financials: Optional[int] = Field(description="Financial metrics score (0-2)", default=0)
    dividend: Optional[int] = Field(description="Dividend information score (0-2)", default=0)
    management: Optional[int] = Field(description="Management quality score (0-2)", default=0)
    ownership: Optional[int] = Field(description="Ownership structure score (0-2)", default=0)
    sustainability: Optional[int] = Field(description="Sustainability score (0-2)", default=0)


class ClassifierPrompts: 
    """
    Centralized prompt templates for better readability and maintenance.
    """
    @staticmethod
    def get_tags_prompt():
        return """You are an expert at classified tags from an article. 
            Your task is to classified tags from 'Article Content' based on 'List of Available Tags'.
            
            List of Available Tags:
            {tags}

            Article Content:
            {body}
            
            Note:
            - ONLY USE the tags listed on 'List of Available Tags'. 
            - DO NOT create, modify, or infer new tags that are not explicitly provided.

            Tag Selection Rules:
            - Identify AT MOST 5 relevant tags from the 'List of Available Tags'.
            - The number of tags should be based on actual relevance, not forced to be 5.
            - If only 1, 2, 3, or 4 tags are relevant, select accordingly.

            Specific Tagging Instructions:
            - `IPO` → Use ONLY for upcoming IPOs. DO NOT apply to past IPO mentions.
            - `IDX` → Use for news related to Indonesia Stock Exchange (Bursa Efek Indonesia).
            - `IDX Composite` → Use only if the article discusses the price or performance of IDX/Indeks Harga Saham Gabungan.
            - `Sharia Economy` → Use if the article mentions Sharia (Syariah) companies or economy.

            Ensure to return the selected tags as a following JSON format.
            {format_instructions}
        """
    
    @staticmethod
    def get_tickers_prompt():
        return """You are an expert financial analyst for classified tickers for Indonesia Stock Market (IDX) summary article. 
            Your task is to classified tickers company from 'Article Content' based on 'List of Available Tickers'.
            
            List of Available Tickers:
            {tickers}

            Article Content:
            {body}

            Ticker Extraction Rules:
            - Identify all tickers that are explicitly mentioned in the 'Article Content'.
            - Do NOT modify, infer, or abbreviate ticker symbols.
            - Ensure to match company name with the correct tickers symbol provided on 'List of Available Tickers'.

            Please Ensure to return the selected tickers as a following JSON FORMAT.
            {format_instructions}
        """
    
    @staticmethod
    def get_subsectors_prompt():
        return """You are an expert at classified subsector from an article. 
            Your task is to classified subsector from 'Article Content' based on 'List of Available Subsectors'.
            
            List of Available Subsectors:
            {subsectors}

            Article Content:
            {body}

            Note:
            - ONLY USE the subsectors listed on ' List of Available Subsectors'. 
            - DO NOT create, modify, or infer new subsectors that are not explicitly provided.

            Subsector Selection Rules:
            - Identify ONE most relevant subsector based on the article content.
            - If multiple subsectors seem relevant, choose the most specific and dominant one.
            - If no appropriate subsector applies, return an empty string.

            Ensure to return the selected subsectors as a following JSON format.
            {format_instructions}
        """
    
    @staticmethod
    def get_sentiment_prompt():
        return """You are an expert at classified sentiment from an article. 
            Your task is to classified sentiment from 'Article Content' based on 'Sentiment Rules'.
            
            Article Content:
            {body}

            Note:
            - Sentiment Classification (Bullish, Bearish, Neutral)
            - Classify the sentiment of the 'Article Content' from the perspective of Indonesia's stock investors.

            Sentiment Rules:
            - Classify the article into one of three categories and do not make things up:
            - "Bullish" → Indicates positive or optimistic sentiment toward stocks.
            - "Bearish" → Indicates negative or pessimistic sentiment toward stocks.
            - "Neutral" → Indicates a balanced or uncertain outlook.
            
            Ensure to return the sentiment as a following JSON format.
            {format_instructions}
        """

    @staticmethod
    def get_dimension_prompt():
        return """You are an expert at classified for dimension from an article. 
            Your task is to classified each dimension from 'Article Content' based on 'Dimension Classification Rule'.

            Article Title:
            {title}

            Article Content:
            {body}

            List of Dimension News Classifications:
            - valuation, future, technical, financials, dividend, management, ownership, sustainability

            Dimension Classification Criteria:
            - valuation → Must include numeric impacts on valuation metrics (P/E, EBITDA, etc.) or events causing ≥2% market cap change in a single trading day.
            - future → Must contain forward-looking statements with specific timelines, numeric projections, official company guidance, or analyst revisions that change growth/earnings estimates by ≥5%.
            - technical → Must report abnormal trading volume (≥2× average) or price movement (±3% in one session) with clear technical patterns or significant support/resistance breakthroughs.
            - financials → Must discuss financial metric changes ≥5% year-over-year, unexpected earnings/revenue results, or material financial structure changes (debt, equity, assets).
            - dividend → Must relate to dividend policy changes, dividend announcements, payout ratio changes ≥3%, or events affecting dividend sustainability (cash flow, earnings coverage).
            - management → Must cover C-suite/board changes, significant insider trading (> $1M), or major executive compensation/governance policy shifts.
            - ownership → Must report ownership changes exceeding 1% of outstanding shares, significant institutional investor actions, or material short interest changes (>20%).
            - sustainability → Must discuss quantifiable ESG impacts, formal sustainability initiatives with specific goals, or ESG rating changes from major agencies.

            Dimension Classification Rules:
            - Assign a classification value (0, 1, 2) for each category:
            - 0 → Not related.
            - 1 → Slightly related.
            - 2 → Highly related.

            - Special Conditions:
            - If the news mentions company financial sustainability, set sustainability = 0.
            - If the news mentions total dividend amount OR if another classification is highly related, set dividend = 0.
         
            Ensure to return the scores dimension as a following JSON format.
            {format_instructions}
        """
    
    @staticmethod
    def get_scoring_prompt():
        return """You are an expert financial analyst for scoring Indonesia Stock Market (IDX) summary article. 
            Your task is to score article summary, based solely on a brief two-sentence summary. 
            Your evaluation is based on the provided 'Scoring Criteria'.

            Scoring Criteria:
            {criteria}

            Article Summary: 
            {body}

            Note:
            - Take a look at criteria first before begin to score the summary article

            Ensure to return the article score in following JSON format.
            {format_instructions} 
        """
    
    @staticmethod
    def get_summarize_prompt():
        return """You are an expert financial analyst for summarizing Indonesia Stock Market (IDX) article. 
            Your task is to generate summary and title based on the article content.

            Article Content:
            {article}

            Note:
            - For the title: Create a one sentence title that is not misleading and gives general understanding.
            - For the body: Provide a concise, maximum 2 sentences summary highlighting main points, key events, and financial metrics.
              And if there is company mentions, maintain the format 'Company Name (TICKER)'.

            Ensure to return the title and summary in the following JSON format.
            {format_instructions}
        """












