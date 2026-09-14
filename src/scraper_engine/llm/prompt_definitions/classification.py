from pydantic import Field, BaseModel
from typing   import List, Optional


class TagsClassification(BaseModel):
    """
    Schema for classifying tags from a financial article.
    The model must select tags only from the provided 'List of Available Tags' and return those most relevant to the article content.
    """
    tags: List[str] = Field(
        description="List of at most 5 relevant tags chosen strictly from the provided list. Do not create or infer new tags."
    )
    explanation: str = Field(description="Your reason why you classified your each tags, clearly state your reason for each tags classified")

class SubsectorClassification(BaseModel):
    """
    Schema for classifying the primary subsector from a financial article.
    The model must select the subsector strictly from the provided 'List of Available Subsectors'.
    """
    subsector: List[str] = Field(
        description="Most relevant subsector chosen strictly from the 'List of Available Subsectors'"
    )
    explanation: str = Field(
        description="Explain the reasoning Why the subsector being assigned"
    )

class SentimentClassification(BaseModel):
    """
    Schema for classifying sentiment from a financial article.
    The sentiment must reflect explicit mentions of stock price trends 
    or investor sentiment in the context of Indonesia's stock market.
    """
    sentiment: str = Field(
        description=(
            "Sentiment classification from the perspective of an equity "
            "investor on IDX or SGX. Must be exactly one of: Bullish, Bearish, "
            "Neutral, Not Applicable. Base classification on investor "
            "impact of the content. Return 'Not Applicable' only when "
            "the summary contains no financial performance dimension "
            "whatsoever."
        )
    )
    explanation: str = Field(
        description=(
            "Step-by-step explanation covering: "
            "1. PERFORMANCE DIMENSION: whether a financial metric or "
            "investor-relevant event is present and why. "
            "2. INVESTOR SIGNALS: each material signal and its direction. "
            "3. SIGNAL WEIGHT: which direction dominates and why. "
            "4. CLASSIFICATION DECISION: the chosen category and the "
            "exact evidence from the summary that determined it."
        )
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

    reasoning: str = Field(
        description='Reasoning why you assign each class with that specific number'
    )


class ClassifierPrompts: 
    """
    Centralized prompt templates for better readability and maintenance.
    """
    @staticmethod
    def get_system_tags_prompt() -> str:
        return """
            You are an expert at classifying tags from financial articles.
            Your task is to classify tags from the provided article based on the List of Available Tags.

            Constraints:
            - ONLY USE the tags listed in the List of Available Tags.
            - DO NOT create, modify, or infer new tags not explicitly provided.
            - Classify STRICTLY based on actual relevance to the article content.
            - If uncertain, do not include the tag.
            - Select AT MOST 5 relevant tags. Do not force 5 — if only 1, 2, 3, or 4 are relevant, select accordingly.

            Tag Ordering Rule:
            - Derive primary tags from the Article Title first. These represent the main highlight of the article.
            - Then supplement with additional tags from the Article Body only if they are strongly and directly relevant.
            - The final tag list must reflect this order: title-derived tags appear before body-derived tags.

            Specific Tagging Instructions:
            - `IPO` → Use ONLY for upcoming IPOs. DO NOT apply to past IPO mentions.
            - `IDX` → Use for news related to Indonesia Stock Exchange (Bursa Efek Indonesia).
            - `IDX Composite` → Use only if the article discusses the price or performance of IDX/IHSG.
            - `Sharia Economy` → Use if the article mentions Sharia companies or economy.
        """

    @staticmethod
    def get_user_tags_prompt() -> str:
        return """
            List of Available Tags:
            {tags}

            Article Title:
            {title}

            Article Body:
            {body}

            Ensure the return in the following JSON format.
            {format_instructions}
        """
    
    @staticmethod
    def get_system_subsectors_prompt() -> str:
        return """
            You are an expert financial analyst specializing in classifying subsectors for financial articles.
            Your task is to determine the correct subsector for the given article summary using only options from the List of Available Subsectors.

            Instructions:
            - Read carefully both the List of Available Subsectors and the Article Summary before deciding.
            - Classify the subsector based only on the List of Available Subsectors.
            - DO NOT infer the company's business from its name alone. A company named "X Holdings" is not necessarily in real estate or finance.
            - Classify the subsector based on the PRIMARY COMPANY's core business, NOT based on the event type (legal cases, management changes, fraud charges, etc.).
            - DO NOT CREATE, MODIFY, or INFER new subsectors not explicitly provided in the List of Available Subsectors.
            - Identify ONE most relevant subsector based on the Article Summary.
            - If multiple subsectors seem relevant, choose the most specific and dominant one.
        """

    @staticmethod
    def get_user_subsectors_prompt() -> str:
        return """
            List of Available Subsectors:
            {subsectors}

            Article Title:
            {title}

            Article Summary:
            {body}

            Ensure to return the selected subsectors as a following JSON format.
            {format_instructions}
        """

    @staticmethod
    def get_sentiment_system_prompt(market: str = "idx"):
        market_context = {
            "idx": """
                Market Context: Indonesian Stock Exchange (IDX)
                Regulatory body: OJK (Otoritas Jasa Keuangan)
                Common article language: Indonesian and English
                Key sector signals to watch:
                - Commodity companies: production volume, export duties,
                royalty payments, commodity price exposure
                - State-owned enterprises (BUMN): profit figures,
                state contribution amounts, privatization signals
                - Conglomerates: subsidiary performance, holding
                company earnings, cross-ownership changes
                Not Applicable examples specific to IDX:
                - PNBP filing notices with no accompanying metrics
                - OJK compliance acknowledgments
                - AGM scheduling with no resolutions affecting earnings
            """,
            "sgx": """
                Market Context: Singapore Exchange (SGX)
                Regulatory body: MAS (Monetary Authority of Singapore)
                Common article language: English
                Key sector signals to watch:
                - REITs and property trusts: distribution per unit (DPU)
                changes, net asset value (NAV), occupancy rates,
                debt-to-asset ratio, acquisition or divestment of
                properties
                - Financial services: net interest margin, loan growth,
                non-performing loan ratio, capital adequacy
                - Manufacturing and logistics: order book, utilization
                rates, contract wins or losses
                Not Applicable examples specific to SGX:
                - SGXNet mandatory form submissions with no metrics
                - Board appointment confirmations with no strategic signal
                - Annual report filing notices with no disclosed results
            """
        }

        return f"""
            You are an expert financial analyst specializing in Asian
            equity markets, with deep knowledge of both the Indonesian
            Stock Exchange (IDX) and the Singapore Exchange (SGX).

            Your task is to classify the investor sentiment of a financial
            news summary. Classify from the perspective of an equity
            investor making a buy, sell, or hold decision on the subject
            company.

            {market_context.get(market, market_context["idx"])}

            CLASSIFICATION RULES:

            Bullish:
            The summary contains signals that a reasonable equity investor
            would interpret as net positive for the company's earnings
            trajectory, valuation, or market position. This includes:
            - Profit, revenue, or distribution growth, especially above
            prior period or market expectations
            - New contracts, market share gains, or strategic expansions
            - Dividend or distribution announcements or increases
            - Index inclusion or credit rating upgrades
            - Positive resolution of regulatory or legal issues
            - Forward guidance raised above prior estimates
            - For REITs specifically: DPU increase, occupancy rate
            improvement, accretive acquisition
            - Strategic announcements (planned IPOs, acquisitions under
            negotiation, expansion targets) qualify as Bullish only
            when the article presents them as credible and near-term.
            Speculative or conditional announcements must be noted as
            such in the reasoning and weighted accordingly against
            any execution risk signals present in the same article.

            Bearish:
            The summary contains signals that a reasonable equity investor
            would interpret as net negative. This includes:
            - Profit, revenue, or distribution decline, especially below
            expectations
            - Margin compression without offsetting growth
            - Dividend or distribution cuts or suspension
            - Index exclusion, credit downgrades, or delisting risk
            - Regulatory penalties, investigations, or sanctions
            - Governance failures or material management instability
            - Forward guidance lowered below prior estimates
            - Material debt increase without corresponding growth
            - For REITs specifically: DPU decrease, occupancy decline,
            dilutive acquisition, NAV erosion

            Neutral:
            A financial performance dimension exists but produces no clear
            directional signal. This includes:
            - Results explicitly in line with prior period or consensus
            - Growth in one metric fully offset by decline in another
            - Credit rating affirmed with no change to outlook
            - Guidance reaffirmed with no revision
            - For REITs: DPU unchanged, occupancy stable

            Not Applicable:
            No financial performance dimension exists. The article is
            purely procedural, structural, or administrative with no
            metric that changes an investor's assessment of the company.

            CRITICAL RULES:
            - Base classification solely on what the summary explicitly
            states. Do not infer beyond the content.
            - Classify on investor impact, not on article tone or
            language style.
            - Do not default to Not Applicable when uncertain. If any
            metric with a clear direction is present, classify
            directionally.
            - Do not use Neutral as a fallback for low confidence.
            Neutral requires explicit evidence that signals cancel out
            or are flat.
            - A regulatory obligation is Not Applicable only if no
            performance metric accompanies it. If a performance metric
            is present, classify based on that metric.
        """
    
    @staticmethod
    def get_sentiment_user_prompt():
        return """
            Article Title:
            {title}
            
            Article Summary:
            {body}

            Before classifying, read carefully through the following steps.
            This reasoning will not appear in the final output.

            1. PERFORMANCE DIMENSION: Does this summary contain any
            financial metric, corporate event, or forward signal that
            affects an investor's view of the company's earnings
            trajectory or valuation? If no, the classification is
            Not Applicable. Stop here.

            2. INVESTOR SIGNALS: List every explicit signal in the summary
            that an equity investor would consider material. For each
            signal state whether it is positive, negative, or flat.

            3. SIGNAL WEIGHT: Which signals are most material to an
            investment decision? Do positive signals clearly dominate,
            do negative signals clearly dominate, or do they cancel out?

            4. CLASSIFICATION DECISION: Based on steps 1 through 3, state
            which category applies and quote the specific evidence from
            the summary that determined it.

            Return your classification in the following JSON format.
            {format_instructions}
        """

    @staticmethod
    def get_system_dimension_prompt() -> str:
        return """
            You are an expert at classifying dimensions from financial articles.
            Your task is to classify each dimension from the article content based on the rules below.

            List of Dimension Classifications:
            - valuation, future, technical, financials, dividend, management, ownership, sustainability

            Dimension Classification Criteria:
            - valuation → Must include numeric impacts on valuation metrics (P/E, EBITDA, etc.) or events causing ≥2% market cap change in a single trading day.
            - future → Must contain forward-looking statements with specific timelines, numeric projections, official company guidance, or analyst revisions that change growth/earnings estimates by ≥5%.
            - technical → Must report abnormal trading volume (≥2× average) or price movement (±3% in one session) with clear technical patterns or significant support/resistance breakthroughs.
            - financials → Must discuss financial metric changes ≥5% year-over-year, unexpected earnings/revenue results, or material financial structure changes (debt, equity, assets).
            - dividend → Must relate to dividend policy changes, dividend announcements, payout ratio changes ≥3%, or events affecting dividend sustainability.
            - management → Must cover C-suite/board changes, significant insider trading (> $1M), or major executive compensation/governance policy shifts.
            - ownership → Must report ownership changes exceeding 1% of outstanding shares, significant institutional investor actions, or material short interest changes (>20%).
            - sustainability → Must discuss quantifiable ESG impacts, formal sustainability initiatives with specific goals, or ESG rating changes from major agencies.

            Dimension Classification Rules:
            - Assign a classification value (0, 1, 2) for each category:
            - 0 → Not related.
            - 1 → Slightly related.
            - 2 → Highly related.

            Special Conditions:
            - If the news mentions company financial sustainability, set sustainability = 0.
            - If the news mentions total dividend amount OR if another classification is highly related, set dividend = 0.
        """

    @staticmethod
    def get_user_dimension_prompt() -> str:
        return """
            Article Title:
            {title}

            Article Content:
            {body}

             Ensure to return the scores dimension as a following JSON format.
            {format_instructions}
        """
