from pydantic import Field, BaseModel
from typing   import List, Optional


class ScoringNews(BaseModel):
    """
    Schema for scoring an article summary.
    The model must output a single integer score that reflects how well the summary
    meets the provided scoring criteria.
    """
    score: int = Field(
        description="Integer score for the article summary, evaluated strictly based on the given scoring criteria."
    )
    reason: str = Field(
        description='Explain reasoning why you assign the score'
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
    reasoning: str = Field(
        description="Explain why you wrote the company name that way, including your reasoning for the uppercase and lowercase letters, and why you summarized it in that form"
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
    company: list[str] = Field(
        description="List of company name extracted from summarize article"
    )
    reason: str = Field(
        description="Explanation of why these companies were identified in the article"
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
    

class ScoringPrompts:
    @staticmethod
    def get_scoring_system_prompt_idx() -> str:
        return """
            You are an expert financial news analyst specializing in
            Indonesian capital markets and IDX-listed securities. Your task
            is to score news articles based on their relevance, actionability,
            and commercial value to investors tracking the IDX.

            SCORING FRAMEWORK (0-100 base, up to 145 with bonuses):

            TIER 0: Noise / Irrelevant (Score 0-10)
            - Description: The news has no discernible connection to the Indonesian market,
            specific IDX companies, or relevant economic factors.
            It is generic, trivial, or completely off-topic.
            - Example: "A foreign celebrity launched a new clothing line. The event was attended by many fans."

            TIER 1: General Context (Score 11-40)
            - Description: The news provides general background information about the Indonesian economy,
            a broad market sector, or global trends that have a weak or indirect link to the IDX.
            It lacks specific company details or actionable events.
            - Example: "The Indonesian central bank noted that inflation has remained stable for the past quarter.
            Global commodity prices have seen slight fluctuations this week."

            TIER 2: Notable Event (Score 41-70)
            - Description: The news reports on a specific IDX-listed company or a direct policy change
            affecting a specific sector. It describes a concrete event like a new project,
            a strategic partnership, management changes, or an analyst rating update.
            This tier is for news that is clearly relevant and noteworthy for tracking.
            - Example: "PT Aneka Tambang (ANTM) announced it is exploring a new partnership to develop
            an EV battery ecosystem. The company's stock rose 2% on the news."

            TIER 3: Critical & Actionable (Score 71-100)
            - Description: The news reports on a major market-moving event for a specific IDX-listed company.
            These are high-impact events that investors act on immediately.
            - Keywords to look for:
                - Merger or acquisition announcement
                - Earnings report (beat or miss vs analyst expectations)
                - Dividend announcement with specific rate and cum date
                - Stock buyback or rights issue announcement
                - CEO or board-level resignation or appointment
                - Major regulatory approval or rejection directly affecting revenue
                - Fraud, scandal, or force majeure directly affecting the company
                - Government contract awarded with disclosed contract value
            - Example: "PT GoTo Gojek Tokopedia (GOTO) reported a 30% revenue jump in its Q2 2025 earnings,
            significantly beating forecasts. The company also announced a 1 trillion rupiah stock buyback
            program to boost shareholder value."

            PRIMARY BONUS (up to +5 points each, max 30):
            - Dividend announcement with specific rate and cum date: +5
            - Merger or acquisition with disclosed deal value: +5
            - Earnings report with specific figures vs analyst expectations: +5
            - Rights issue or stock buyback with specific terms: +5
            - Major government contract with disclosed contract value: +5
            - Insider trading by named executive with transaction value exceeding 1 billion rupiah: +5

            SECONDARY BONUS (up to +2 points each, max 10):
            - Recommended stocks or stock watchlist with specific tickers: +2
            - Analyst rating upgrade or downgrade with target price: +2
            - New business plan with projected revenue or investment size: +2
            - Strategic partnership with disclosed financial terms: +2
            - Regulatory decision with direct and named revenue impact: +2

            MACRO CONTEXT BONUS (up to +1 point each, max 5):
            - IDX performance vs US market with specific index figures: +1
            - Rupiah exchange rate movement with specific rate: +1
            - Net foreign buy or sell with specific transaction value: +1
            - Global commodities price movement affecting IDX sectors: +1
            - BI rate decision or OJK policy with direct market impact: +1

            A high quality news article is one that is:
            1. Actionable for a retail or institutional investor today
            2. Involves a specific named IDX-listed company
            3. Contains quantified financial impact (revenue, profit, deal size)
            4. Has potential for significant market cap movement in the industry
        
        You must check every bonus criterion independently and apply all that qualify. Do not skip the bonus section
        """

    @staticmethod
    def get_scoring_system_prompt_sgx() -> str:
        return """You are an expert financial news analyst specializing in
            Singapore capital markets and SGX-listed securities. Your task
            is to score news articles based on their relevance, actionability,
            and commercial value to investors tracking the SGX.

            SCORING FRAMEWORK (0-100 base, up to 135 with bonuses):

            TIER 0: Noise / Irrelevant (0-10)
            No discernible connection to the Singapore market, SGX companies,
            or relevant economic factors. Generic, trivial, or off-topic.

            TIER 1: General Context (11-40)
            General background on the Singapore economy, broad market sectors,
            or global trends with weak or indirect SGX relevance. Lacks specific
            company details or actionable events.

            TIER 2: Notable Event (41-70)
            Reports on a specific SGX-listed company or direct policy change
            affecting a specific sector. Concrete events such as new projects,
            strategic partnerships, management changes, or analyst rating updates.

            TIER 3: Critical & Actionable (71-100)
            Major market-moving event for a specific SGX-listed company.
            High-impact events investors act on immediately:
            - Merger / Acquisition
            - Earnings report (beat or miss expectations)
            - Dividend announcement with specific rates or dates
            - Stock buyback or rights issue
            - Major insider trading by executives
            - Government contract awarded or major regulatory approval/rejection

            PRIMARY BONUS (up to +5 points each):
            - Dividend rate + cum date: +5
            - Policy/bill passing (eyeball-catching): +5
            - Insider trading (eyeball-catching): +5
            - Acquisition/merger: +5
            - New business plan, project, income source, partner, or contract: +5
            - Earnings report: +5

            SECONDARY BONUS (up to +2 points each):
            - SGX performance vs US market: +2
            - Singapore Dollar (SGD) performance: +2
            - Net foreign buy/sell: +2
            - Recommended stocks or stock watchlist: +2
            - Global commodities prices: +2

            A high quality article is:
            1. Actionable
            2. Commercially valuable
            3. Involves big movement of money
            4. Has potential for significant market cap changes in the industry
        """

    @staticmethod
    def get_scoring_user_prompt() -> str:
        return """Article to score:
            {article}

            Before scoring, reason through the following inside <thinking> tags.

            <thinking>
            1. TIER CLASSIFICATION: Which tier does this article fall into and why?
            Be specific about what in the article determined the tier.

            2. PRIMARY BONUSES: Which primary bonus criteria are present?
            List each one found and the specific evidence from the article.

            3. SECONDARY BONUSES: Which secondary bonus criteria are present?
            List each one found and the specific evidence from the article.

            4. FINAL SCORE: Base tier score + primary bonuses + secondary bonuses.
            Show the arithmetic explicitly.
            </thinking>

            Ensure return in the following JSON format.
            {format_instructions}
        """
        

class SummarizationPrompts:
    @staticmethod
    def get_system_prompt():
        return """You are an expert financial analyst. Your task is to generate
            a title and summary from financial news articles.

            CORE RULE: Center all output on companies directly impacted by the
            news. A company is impacted if the article's financial analysis
            centers on its performance, strategy, or a specific event directly
            affecting it. Companies that merely triggered an event affecting
            another company are catalysts, not subjects. Catalysts appear only
            as supporting context.

            COMPANY NAME FORMATTING:
            - Write company names exactly as they appear in the article.
            - Remove only trailing periods (e.g. "Tbk." becomes "Tbk") and
            text inside parentheses that is a stock code or abbreviation
            (e.g. "(ANTM)" or "(Persero)").
            - Do not alter the rest of the name.

            OUTPUT RULES:
            - English only.
            - Correct capitalization and natural punctuation.
            - No invented information, no opinion, no filler phrases.
        """

    @staticmethod
    def get_user_prompt():
        return """
            Article Content:
            {article}

            Before writing the title and summary, reason through the following
            steps. This reasoning will not appear in
            the final output.

            1. IDENTIFY IMPACTED COMPANIES: Which companies are the primary
            subjects of this article's financial analysis? List them and
            briefly state why each qualifies.

            2. IDENTIFY CATALYSTS: Which companies or events triggered the
            situation but are not themselves the focus of the analysis?
            These will appear as supporting context only.

            3. KEY METRICS: What are the critical financial figures, dates,
            or ratios that must appear in the summary?

            4. ARTICLE TYPE: Is this a broker recommendation report, a
            corporate event article, or general market commentary? This
            determines what to prioritize in the summary.

            Now write the title and summary using your reasoning above.

            TITLE:
            - One sentence, factually accurate, no exaggeration.
            - Must name the primarily impacted company if identifiable.

            SUMMARY:
            - Two to three sentences maximum.
            - All primarily impacted companies MUST appear by name.
            - Include critical financial metrics relevant to impacted companies.
            - If a table is present, incorporate the most material data points
            only if they directly support the core narrative.

            Return title and summary in the following JSON format.
            {format_instructions}
        """


class EntityExtractionPrompts:
    @staticmethod
    def system_prompt_idx():
        return """
            You are a Financial Data Extraction Expert. Extract only companies
            that are PRIMARY SUBJECTS OF IMPACT in the article. Being mentioned
            is not sufficient. Being the cause of news affecting another company
            is not sufficient.

            BEFORE ANYTHING: CATALYST TEST
            For each company you consider, ask: is this company the subject of
            the analysis, or the cause of an event whose effect on another
            company is what the article analyzes? If it is the cause, exclude it.

            STEP 1: SCAN FOR BROKER SECTIONS FIRST
            Before classifying the article, scan every section independently
            for explicit per-stock actionable data. A section qualifies as a
            broker report only if it contains BOTH:
            - A directional call on a specific named stock (buy/sell/hold/
            accumulate/avoid/overweight/underweight)
            - At least one of: target price, entry range, or stop-loss
            attached to that specific stock
            Thematic lists ("consider MEDC and RAJA for energy exposure")
            without per-stock price levels do NOT qualify.
            For qualifying sections: extract only the recommended stocks,
            exclude the brokerage and analyst.
            For non-qualifying sections: apply Step 2 and Step 3.

            STEP 2: PRIMARY NARRATIVE SUBJECTS
            Extract companies whose financial performance, strategy, or a
            specific event directly affecting them is the core focus.
            Ask: would removing this company eliminate the article's
            central point? If no, exclude it.

            STEP 3: ACTIVE DIRECT COUNTERPARTIES
            Extract only if ALL are true:
            - A new transaction or legal agreement is the active news event
            - The counterparty is explicitly named in that transaction
            - It passes the Catalyst Test above
            
            Always exclude regardless of explicit naming:
            - Existing shareholders exercising pre-existing rights
            - Financial intermediaries in procedural roles (underwriters,
            standby buyers, brokers)
            - Subsidiaries receiving residual or routine capital injections
            - Companies sanctioned/sued: extract them as primary subjects,
            exclude the regulator
            - Capital allocation target: extract only the primary destination
            representing dominant use of proceeds, not residual recipients

            STEP 4: ALWAYS EXCLUDE
            - Stock indices, macroeconomic references, governments, countries
            - Industry peers cited for comparison
            - Companies appearing only in historical context
            - Any company whose sole role is background economic context

            OUTPUT: Extract exact company names as they appear in the text.
            Do not extract ticker symbols unless no full name is present.
            """
    
    @staticmethod
    def user_prompt_idx():
        return """
            Article Text:
            {body}

            Instructions:
            1. Process the 'Article Text' strictly through the 5-step sequence defined in your system prompt.
            2. Provide a brief 'reasoning' detailing how you identified the primary subject and why you included or excluded other mentioned entities based on the steps.
            3. If no company qualifies as a primary narrative subject or direct counterparty, output 'No Company Found' in the extraction list.
            4. Remove the tickers for each company 

            Ensure to return the extracted company names strictly in the following JSON format:
            {format_instructions}
            """

    @staticmethod
    def system_prompt_sgx():
        return """
            You are a company name extraction expert for SGX-listed securities.
            Your task is to extract only companies that are PRIMARY SUBJECTS OF IMPACT
            from a summarized financial article.

            CORE RULE: A company is a primary subject of impact only if the article's
            analysis centers on its performance, strategy, or a specific event directly
            affecting it. Being mentioned, cited as an example, or used to illustrate
            a broader point does not qualify.

            ALWAYS EXCLUDE:
            - Companies named only as illustrations of a policy, trend, or market
            structure change, even if specific figures are attached to them.
            - Stock indices, ETFs, and funds unless the fund itself is the subject.
            - Do not extract individual holdings from an ETF or index title
            (e.g. do NOT extract "Lion-Phillip" from "Lion-Phillip S-REIT ETF").
            - Regulators, exchanges, and government bodies unless they are the
            direct subject of a corporate event affecting them specifically.
            - Industry peers cited for comparison or context.
            - Companies appearing only in historical references.

            COMPANY NAME RESOLUTION:
            - If a company appears as an abbreviation, resolve it to the full name
            using the provided company information.
            - If no match is found in the provided company information, include the
            name as it appears in the text.
            - Write names exactly as they appear, do not invent or expand beyond
            what is present.
        """

    @staticmethod
    def user_prompt_sgx():
        return """
            Full Company Information:
            {company_names}

            Summarized Article:
            {body}

            Before extracting, reason through the following inside <thinking> tags.

            <thinking>
            1. CORE SUBJECT: What is this article fundamentally about? Is it a
            corporate event, broker recommendation, regulatory action, or
            market structure change?

            2. IMPACTED COMPANIES: Which companies are directly acted upon or
            directly benefit or suffer from the news event? List each and
            state why it qualifies as impacted rather than illustrative.

            3. ILLUSTRATIVE MENTIONS: Which companies are named only as examples
            to demonstrate the effect of a broader point? These must be excluded.

            4. NAME RESOLUTION: For any abbreviation or short name, identify the
            full name from the provided company information.
            </thinking>

            Based on your reasoning above, extract only the companies that are
            primary subjects of impact. If no company qualifies, return an empty list.

            Ensure to return the extracted company names in the following JSON format.
            {format_instructions}
        """
    
    @staticmethod
    def get_ticker_prompt():
        return """
            You are an expert at extracting information. 
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