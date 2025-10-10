from pydantic import Field, BaseModel
from typing   import List, Optional


# Define Pydantic models for each classification type
class ScoringNews(BaseModel):
    """
    Schema for scoring an article summary.
    The model must output a single integer score that reflects how well the summary
    meets the provided scoring criteria.
    """
    score: int = Field(
        description="Integer score for the article summary, evaluated strictly based on the given scoring criteria."
    )

class SummaryNews(BaseModel):
    """
    Schema for generating a concise financial news summary.
    The model must provide one clear, accurate title and a maximum two-sentence summary
    based only on the article content.
    """
    title: str = Field(
        description="A single-sentence title that accurately reflects the article without exaggeration or misleading language."
    )
    summary: str = Field(
        description="A concise maximum two-sentence summary that captures key events, main points, and any explicitly mentioned financial metrics."
    )

class TagsClassification(BaseModel):
    """
    Schema for classifying tags from a financial article.
    The model must select tags only from the provided 'List of Available Tags' and return those most relevant to the article content.
    """
    tags: List[str] = Field(
        description="List of at most 5 relevant tags chosen strictly from the provided list. Do not create or infer new tags."
    )
    reason: str = Field(description="Your reason why you classified your each tags, clearly state your reason for each tags classified")

class TickersClassification(BaseModel):
    tickers: List[str] = Field(description="List of stock tickers mentioned in the article")

class CompanyNameExtraction(BaseModel):
    """
    Schema for extracting company names mentioned in a summarized financial article.
    The model return only company names as they appear in the text.
    """
    company: List[str] = Field(
        description="List of company name extracted from summarize article"
    )

class CompanyNameTickerExtraction(BaseModel):
    """
    Schema for extracting tickers mentioned in a summarized financial article.
    The model return only tickers as they appear in the text.
    """
    tickers: List[str] = Field(
        description="List of tickers extracted from summarize article"
    )

class SubsectorClassification(BaseModel):
    """
    Schema for classifying the primary subsector from a financial article.
    The model must select the subsector strictly from the provided 'List of Available Subsectors'.
    """
    subsector: List[str] = Field(
        description="Most relevant subsector chosen strictly from the 'List of Available Subsectors'"
    )

class SentimentClassification(BaseModel):
    """
    Schema for classifying sentiment from a financial article.
    The sentiment must reflect explicit mentions of stock price trends 
    or investor sentiment in the context of Indonesia's stock market.
    """
    sentiment: str = Field(
        description="Sentiment of the article as one of: 'Bullish', 'Bearish', 'Neutral', 'Not Applicable."
    )

class DimensionClassification(BaseModel):
    """
    Schema for scoring multiple investment-related dimensions from a financial article.
    Each dimension must be classified with a score of 0 (not related), 1 (slightly related), or 2 (highly related).
    """
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
        return """You are an expert at classifying tags from financial article. 
            Your task is to classifying tags from 'Article Content' based on 'List of Available Tags'.
            
            List of Available Tags:
            {tags}
            
            Article Content:
            {body}
            
            Note:
            - ONLY USE the tags listed on 'List of Available Tags'. 
            - Carefully read each tag and reason its explanation before classify it for 'Article Content'.
            - DO NOT create, modify, or infer new tags that are not explicitly provided.
            - Classify STRICTLY based on actual relevance to the article content.

            Tag Selection Rules:
            - Identify AT MOST 5 relevant tags from the 'List of Available Tags'.
            - Do not force 5 — if only 1, 2, 3, or 4 are relevant, select accordingly.
    
            Specific Tagging Instructions:
            - `IPO` → Use ONLY for upcoming IPOs. DO NOT apply to past IPO mentions.
            - `IDX` → Use for news related to Indonesia Stock Exchange (Bursa Efek Indonesia).
            - `IDX Composite` → Use only if the article discusses the price or performance of IDX/Indeks Harga Saham Gabungan.
            - `Sharia Economy` → Use if the article mentions Sharia (Syariah) companies or economy.

            IMPORTANT:
            - You must select tags ONLY if they are strongly and directly relevant to the article content.
            - If uncertain, do not include the tag.

            Ensure to return the selected tags as a following JSON format.
            {format_instructions}
        """
    
    @staticmethod
    def get_tickers_prompt():
        return """You are an expert financial analyst for classifying tickers for Indonesia Stock Market (IDX) summary article. 
            Your task is to classifying tickers company from 'Article Content' based on 'List of Available Tickers'.
            
            List of Available Tickers:
            {tickers}

            Article Content:
            {body}

            Ticker Extraction Rules:
            - Identify all tickers that are explicitly mentioned in the 'Article Content'.
            - Do NOT modify, infer, or abbreviate ticker symbols.
            - ENSURE to match company name mentioned in 'Article Content' with the correct tickers symbol provided in 'List of Available Tickers'.
            - ENSURE to match ticker name mentioned in 'Article Content' with the correct tickers symbol provided in 'List of Available Tickers'.
            - Extract all tickers you can found on 'Article Content'. 

            Please Ensure to return the selected tickers as a following JSON FORMAT.
            {format_instructions}
        """
    
    @staticmethod
    def get_company_name_prompt():
        return """You are an expert at extracting information. 
            Your task is to extract company name from a summarize article.
        
            Summarize Article:
            {body}

            Instruction:
            - Look carefully 'Summarize Article' and find COMPANY NAME.
            - Extract the exact company name based on 'Summarize Article' do not change it. 
            - Extract all company name you can find.
            - If there is no company name to extract, state 'No Company Found'.

            Ensure to return the extracted company name as a following JSON format.
            {format_instructions}
        """
    
    @staticmethod
    def get_ticker_prompt():
        return """You are an expert at extracting information. 
            Your task is to extract company name ticker from a summarize article.
        
            Summarize Article:
            {body}

            Instruction:
            - Look carefully 'Summarize Article' and find company name ticker.
            - Extract the exact ticker based on 'Summarize Article' do not change it. 
            - Extract all ticker you can find.
            - If there is no ticker to extract, state 'No Ticker Found'.

            Ensure to return the extracted ticker as a following JSON format.
            {format_instructions}
        """
    
    @staticmethod
    def get_subsectors_prompt():
        return """You are an expert financial analyst specializing in classifying subsectors for financial articles.   
            Your task is to determine the correct subsector for the given 'Article Summary' using only option in the 'List of Available Subsectors'.  

            List of Available Subsectors:
            {subsectors}

            Article Summary:
            {body}

            Instructions:
            - Read carefully both the 'List of Available Subsectors' and the 'Article Summary' before deciding. 
            - Classify subsector of 'Article Summary' based only on 'List of Available Subsectors'. 
            - DO NOT CREATE, MODIFY, or INFER new subsectors that are not explicitly provided on 'List of Available Subsectors'.
            - Identify ONE most relevant subsector based on the 'Article Summary'.
            - If multiple subsectors seem relevant, choose the most specific and dominant one.

            Ensure to return the selected subsectors as a following JSON format.
            {format_instructions}
        """

    @staticmethod
    def get_sentiment_prompt():
        return """You are an expert at classifying sentiment from an article about the Indonesian Stock Market (IDX). 
        Your task is to classify sentiment as Bearish, Bullish, Neutral, or Not Applicable from 'Article Summarize' based on 'Sentiment Rules'.

        Article Summarize:
        {body}

        Note:
        - Classification must only be based on explicit mentions of stock price movement or investor sentiment.
        - If the article does not mention stock prices, stock trends, classify it as "Not Applicable".

        Sentiment Rules:
        - "Bullish" → The article explicitly states that a stock/sector is rising, rallying, in an uptrend, or described as bullish.
        - "Bearish" → The article explicitly states that a stock/sector is falling, declining, in a downtrend, or described as bearish.
        - "Neutral" → The article explicitly states that a stock/sector is stable, flat, sideways, or described as neutral.
        - "Not Applicable" → No explicit mention of stock price movement.

        Output:
        Return the classified in the following JSON format:
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
        return """You are an expert financial analyst specializing in evaluating article summaries. 
            Your task is to assign a score to the given 'Article Summary' based strictly on the 'Scoring Criteria'.

            Scoring Criteria:
            {criteria}

            Article Summary: 
            {body}

            Instructions:  
            - Carefully read the criteria before evaluating the 'Article Summary'.  
            - Base your judgment solely on how well the 'Article Summary' meets the 'Scoring Criteria'.  
            - Be objective and concise in applying the criteria.  

            Ensure to return the article score in following JSON format.
            {format_instructions} 
        """
    
    @staticmethod
    def get_summarize_prompt():
        return """You are an expert financial analyst specializing in summarization article. 
            Your task is to generate a clear title and a concise summary based strictly on the provided 'Article Content'.  
            
            Article Content:
            {article}

            Instruction:
            - Title:  Write a single-sentence title that accurately reflects the article, avoids exaggeration, and provides a clear general understanding.
            - Summary: Write a maximum of two sentences highlighting the key events, main points, and any relevant financial metrics.  
            - Company Mentions: PRESERVE COMPANY NAMES exactly as written in the article. 
            - Ticker Symbols: Include ticker company symbols ONLY IF they are explicitly PRESENT in the article. Do not infer or create ticker symbols.  
            - Relevance: Stay strictly grounded in the article content. Do not invent information or include unrelated topics.  
            - Conciseness: Keep the output factual, focused, and free of unnecessary detail.  

            Note:
            - Keep the COMPANY NAMES capitalization format exactly as written in the 'Article Content'.
            - Return title and summary in english.
            
            Ensure to return the title and summary in the following JSON format.
            {format_instructions}
        """












