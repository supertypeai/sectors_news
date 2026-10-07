from pydantic import Field, BaseModel
from typing import Literal


class SubsectorClassification(BaseModel):
    """
    Schema for classifying the primary subsector from a financial article.
    The model must select the subsector strictly from the provided 'List of Available Subsectors'.
    """
    sub_sector: str = Field(
        description="Most relevant subsector chosen strictly from the 'List of Available Subsectors'"
    )

    # explanation: str = Field(
    #     description="Explain the reasoning Why the subsector being assigned"
    # )


class DimensionClassification(BaseModel):
    """
    Scores the article across investment-related dimensions.

    Every dimension must be assigned exactly one score:
    - 0: Not related
    - 1: Slightly related
    - 2: Highly related

    Each dimension must be evaluated independently based only on information
    explicitly supported by the article.
    """

    valuation: Literal[0, 1, 2] = Field(
        description=(
            "Relevance to company valuation, including valuation multiples, "
            "target prices, valuation changes, or events with a direct material "
            "impact on valuation. 0 = not related, 1 = slightly related, "
            "2 = highly related."
        )
    )

    future: Literal[0, 1, 2] = Field(
        description=(
            "Relevance to forward-looking company prospects, including official "
            "guidance, projections, expansion targets, timelines, or analyst "
            "estimate revisions. 0 = not related, 1 = slightly related, "
            "2 = highly related."
        )
    )

    technical: Literal[0, 1, 2] = Field(
        description=(
            "Relevance to stock-price or trading behavior, including material "
            "price movement, abnormal volume, support or resistance levels, or "
            "other technical-market signals. 0 = not related, "
            "1 = slightly related, 2 = highly related."
        )
    )

    financials: Literal[0, 1, 2] = Field(
        description=(
            "Relevance to financial performance or financial position, including "
            "revenue, profit, margins, cash flow, debt, assets, equity, or other "
            "material financial metrics. 0 = not related, 1 = slightly related, "
            "2 = highly related."
        )
    )

    dividend: Literal[0, 1, 2] = Field(
        description=(
            "Relevance to dividends or shareholder distributions, including "
            "dividend announcements, payout ratios, policy changes, distribution "
            "changes, or dividend sustainability. 0 = not related, "
            "1 = slightly related, 2 = highly related."
        )
    )

    management: Literal[0, 1, 2] = Field(
        description=(
            "Relevance to company management or governance, including material "
            "board or executive changes, significant insider transactions, "
            "executive compensation, or governance developments. "
            "0 = not related, 1 = slightly related, 2 = highly related."
        )
    )

    ownership: Literal[0, 1, 2] = Field(
        description=(
            "Relevance to company ownership, including controlling shareholder "
            "changes, material shareholding transactions, institutional ownership, "
            "or other significant ownership developments. "
            "0 = not related, 1 = slightly related, 2 = highly related."
        )
    )

    sustainability: Literal[0, 1, 2] = Field(
        description=(
            "Relevance to environmental, social, or governance sustainability "
            "topics with measurable impacts, formal targets, initiatives, or ESG "
            "rating changes. General financial sustainability alone does not count. "
            "0 = not related, 1 = slightly related, 2 = highly related."
        )
    )


class ClassificationSchema(BaseModel):
    """
    Combined classification output for a financial news article.

    Tags, sentiment, and dimensions must be classified independently.
    The result of one classification must not be used as evidence for another.
    """
    tags: list[str] = Field(
        description=(
            "Up to 5 strongly relevant tags chosen strictly from the provided "
            "List of Available Tags. Do not create, rename, or infer tags outside "
            "the provided list. Order tags from most relevant to least relevant."
        ),
        max_length=5,
    )

    sentiment: Literal[
        "Bullish",
        "Bearish",
        "Neutral",
        "Not Applicable",
    ] = Field(
        description=(
            "Investor sentiment toward the primary subject company. "
            "Bullish = clear net-positive investor signal; "
            "Bearish = clear net-negative investor signal; "
            "Neutral = meaningful signals exist but are genuinely balanced or flat; "
            "Not Applicable = no meaningful company-level financial, operating, "
            "or valuation signal exists."
        )
    )

    dimension: DimensionClassification = Field(
        description=(
            "Independent relevance scores for each investment-related dimension."
        )
    )


class ClassifierPrompts: 
    """
    Centralized prompt templates for better readability and maintenance.
    """
    @staticmethod
    def get_system_subsectors_prompt() -> str:
        return """
            You are a financial-news subsector classification system.

            Your task is to identify the single most appropriate subsector for the primary
            company discussed in the article.

            You must choose only from the provided List of Available Subsectors.

            Rules:

            - Return exactly one subsector.
            - Never create, rename, modify, or infer a subsector outside the provided list.
            - Classify based on the primary company's core business.
            - Do not classify based primarily on the event described in the news.

            For example:
            - a mining company's rights issue should still be classified according to its
            mining business, not financial services
            - a bank involved in a legal case should still be classified according to its
            banking business
            - a property company's management change should still be classified according
            to its property business

            Do not infer a company's business from its name alone.

            Names containing words such as:
            - Holdings
            - Capital
            - Resources
            - International
            - Group

            do not by themselves establish a subsector.

            Use information explicitly available in the article title and summary to
            identify the company's actual business.

            If several business activities are mentioned, classify according to the
            primary company's dominant or core business rather than a newly announced
            secondary activity.

            If multiple subsectors appear plausible, choose the most specific subsector
            that is clearly supported by the article.
        """

    @staticmethod
    def get_user_subsectors_prompt() -> str:
        return """
            Classify the primary company in the following financial news summary into
            exactly one subsector.

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
    def get_system_classification_prompt() -> str: 
        return """ 
            You are a financial-news classification system for Asian equity markets.

            Your task is to independently produce three classifications from the same
            financial article summary:

            1. tags
            2. sentiment
            3. dimensions

            Follow the provided output schema exactly.

            IMPORTANT:
            Each classification is an independent task.

            Do not use the result of one classification as evidence for another.
            For example:
            - a "Dividend Announcement" tag does not automatically make sentiment Bullish
            - a "Mergers & Acquisitions" tag does not automatically make the future dimension highly related
            - sentiment must not affect dimension scores

            All classifications must be based only on information explicitly supported by
            the article title and summary.

            TAGS

            Select tags only from the provided List of Available Tags.

            Rules:
            - Never create, rename, modify, or infer tags outside the provided list.
            - Select at most 5 tags.
            - Do not force 5 tags. Return only strongly relevant tags.
            - If uncertain about a tag, omit it.
            - Prioritize the main development described by the article title.
            - Add tags based on the summary only when they are directly relevant to the
            main development.
            - Order the tags by relevance, with tags describing the primary development
            appearing first.

            Specific rules, when these tags exist in the available list:
            - IPO: use only for upcoming or ongoing IPO activity, not historical IPO mentions.
            - IDX: use for news directly concerning the Indonesia Stock Exchange.
            - IDX Composite: use only when the article discusses IHSG/IDX Composite
            performance or movement.
            - Sharia Economy: use only when Islamic or Sharia economic activity is
            materially relevant.

            SENTIMENT

            Classify sentiment from the perspective of an equity investor evaluating the
            subject company.

            Allowed classifications:
            - Bullish
            - Bearish
            - Neutral
            - Not Applicable

            Bullish:
            The article contains a clear net-positive signal for earnings, valuation,
            financial position, shareholder return, or competitive position.

            Examples:
            - meaningful profit or revenue growth
            - raised guidance or analyst estimates
            - dividend increase or announcement with positive shareholder impact
            - credit-rating upgrade
            - material contract win or credible expansion
            - improving margins, occupancy, DPU, or other relevant operating metrics

            Bearish:
            The article contains a clear net-negative signal.

            Examples:
            - declining earnings or revenue
            - margin deterioration
            - dividend reduction or suspension
            - credit-rating downgrade
            - regulatory sanction or material investigation
            - material governance problems
            - lowered guidance
            - significant financial deterioration or debt stress

            Neutral:
            A financial or operating signal exists, but the overall directional impact is
            genuinely balanced or flat.

            Use Neutral only when:
            - results are explicitly stable or in line, or
            - meaningful positive and negative signals substantially offset each other.

            Do not use Neutral merely because confidence is low.

            Not Applicable:
            Use when the article has no meaningful company-level financial, operating, or
            valuation signal and is primarily procedural, administrative, or structural.

            Examples may include:
            - meeting scheduling with no material resolution
            - routine filing notices
            - administrative board confirmations with no strategic implication

            Rules:
            - Judge investor impact, not the emotional tone of the writing.
            - Planned, conditional, or speculative events should be weighted according to
            their actual status.
            - Keep analyst opinions and management expectations attributed.
            - Do not infer effects not stated or reasonably established by the summary.

            DIMENSIONS

            Score every dimension independently using:
            - 0 = not related
            - 1 = slightly related
            - 2 = highly related

            Dimensions:

            valuation
            - Numeric valuation measures such as P/E, EV/EBITDA, target prices, valuation
            changes, or events with a direct material effect on company valuation.

            future
            - Material forward-looking information such as numeric projections, official
            guidance, expansion targets with timelines, or analyst estimate revisions.

            technical
            - Material share-price or trading behavior such as a >=3% single-session move,
            abnormal volume, technical support/resistance, or significant market
            technical signals.

            financials
            - Material changes in revenue, profit, margins, debt, assets, equity, cash flow,
            or other financial-statement metrics.

            dividend
            - Dividend announcements, payout policy, payout-ratio changes, distribution
            changes, or information materially affecting dividend sustainability.

            management
            - Material C-suite or board changes, significant insider transactions,
            executive compensation, or major governance changes.

            ownership
            - Material changes in company ownership, controlling shareholders,
            institutional holdings, or significant shareholding transactions.

            sustainability
            - Quantifiable ESG impacts, formal sustainability initiatives with measurable
            targets, or ESG-rating changes.

            Dimension rules:
            - Score based on actual relevance, not keyword presence.
            - Mentioning a concept in passing should not receive a score of 2.
            - Multiple dimensions may receive a score of 2 when independently justified.
            - "Financial sustainability" in the general sense of a company's ability to
            continue operating is not an ESG sustainability signal.
        """

    @staticmethod 
    def get_user_classification_prompt() -> str: 
        return """ 
            Classify the following financial news summary.

            Market:
            {market}

            List of Available Tags:
            {tags}

            Article Title:
            {title}

            Article Summary:
            {body}

            Return the tags, sentiment, and dimension classifications using the provided
            structured output schema.

            Do not add information that is not supported by the title or summary.

            RETURN the response in the following JSON SCHEMA:
            {format_instructions}
        """