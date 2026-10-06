from dataclasses import dataclass
from pydantic import BaseModel, Field

from .market_context import MARKET_CONTEXTS

import inspect


@dataclass(frozen=True)
class DevelopmentTerms:
    insolvency_terms: str
    subject_ticker: str
    incidental_tickers: str


DEVELOPMENT_TERMS = {
    "IDX": DevelopmentTerms(
        insolvency_terms="PKPU, bankruptcy",
        subject_ticker='"AAAA.JK"',
        incidental_tickers='"BBBB.JK", "CCCC.JK"',
    ),
    "SGX": DevelopmentTerms(
        insolvency_terms="judicial management, a scheme of arrangement, a moratorium",
        subject_ticker='"A1B.SI"',
        incidental_tickers='"C2D.SI", "E3F.SI"',
    ),
}


class DevelopmentItem(BaseModel):
    title: str = Field(
        description=(
            "Concise factual title describing one distinct real-world development. "
            "Describe what happened, not the article headline. "
            "Do not use vague labels such as 'Company Update' or 'Corporate News'."
        )
    )

    summary: str = Field(
        description=(
            "Concise factual summary consolidating the useful information from all "
            "articles belonging to this development. Keep every figure, currency, "
            "date, and hedge exactly as supplied. Do not speculate, infer missing "
            "facts, or add information not supported by the supplied articles."
        )
    )

    tickers: list[str] = Field(
        default_factory=list,
        description=(
            "Stock tickers directly affected by or directly involved in this "
            "development. Only use tickers present in the supplied article data."
        ),
    )

    supporting_news_ids: list[int] = Field(
        description=(
            "IDs of all supplied news articles that describe this same underlying "
            "development. Every ID must come from the input."
        )
    )


class DevelopmentArticles(BaseModel):
    developments: list[DevelopmentItem] = Field(
        default_factory=list,
        description=(
            "Distinct factual developments identified from the supplied news articles."
        ),
    )

    excluded_news_ids: list[int] = Field(
        default_factory=list,
        description=(
            "News IDs excluded because they do not describe a concrete factual "
            "development. Every input ID appears either here or in at least one "
            "development's supporting_news_ids, never both."
        ),
    )


class DevelopmentPrompts:
    @staticmethod
    def get_system_development_prompt(exchange: str):
        context = MARKET_CONTEXTS[exchange]
        terms = DEVELOPMENT_TERMS[exchange]

        template = inspect.cleandoc(
            """
            You are a financial-news development extraction system for a {market}
            equity-market intelligence product.

            Your task is to transform a batch of news articles into distinct factual
            developments.

            You are NOT writing any brief.
            You are NOT deciding which developments are important.
            You are NOT ranking developments.

            A later stage will evaluate materiality.

            DEFINITION OF A DEVELOPMENT

            A development is a concrete factual change in the state of a company,
            sector, industry, regulation, transaction, operation, ownership
            structure, financial performance, governance situation, legal
            situation, the macroeconomy, or other real-world condition.

            Examples include:
            - a company reports financial results;
            - an acquisition is proposed, agreed, completed, rejected, or approved;
            - a shareholder acquires or disposes of a meaningful stake;
            - a company issues shares, conducts a buyback, or changes its capital
              structure;
            - a regulator or government announces or implements a policy change;
            - a company changes directors or senior management;
            - operations are suspended, disrupted, expanded, or restarted;
            - a company enters restructuring, default, {insolvency_terms},
              litigation, or investigation;
            - a major project reaches a concrete new stage;
            - a central bank makes a rate decision, intervenes in a market, or
              changes its policy tools;
            - the currency, a benchmark bond yield, or a major commodity price
              crosses a level reported as significant by the articles;
            - the government sets or changes a budget, tax, subsidy, or
              macroeconomic assumption;
            - an official economic figure is released (inflation, GDP, trade
              balance, reserves).

            Macroeconomic developments usually have no ticker. Return an empty
            tickers list for them rather than excluding the article.

            A development must be based on a factual event or state change.

            The following are NOT developments by themselves:
            - analyst ratings or target prices;
            - broker recommendations;
            - technical analysis;
            - stock recommendations;
            - generic forecasts or predictions;
            - movements in individual stock prices without an identifiable
              factual catalyst;
            - foreign or domestic investor flow observations in individual stocks
              by themselves;
            - valuation commentary;
            - opinion pieces;
            - generic market outlooks;
            - "stocks to watch" articles;
            - commentary that introduces no new factual event.

            These exclusions cover individual stocks only. A currency move, a
            central bank statement, or a government response reported in the
            same article is a macroeconomic development and must be extracted.

            If an article contains both commentary and a valid factual development,
            extract the factual development and ignore the commentary.

            ILLUSTRATIONS BELOW USE FICTIONAL COMPANIES. Do not reuse their facts.

            Article:
            "Broker upgrades Contoh Tobacco to Buy after H1 profit rises"

            Valid development:
            "Contoh Tobacco reports H1 profit increase"

            Do NOT create:
            "Broker upgrades Contoh Tobacco to Buy"

            ONE ARTICLE MAY CONTAIN ZERO, ONE, OR MULTIPLE DEVELOPMENTS

            Do not assume one article equals one development.

            An article may combine several unrelated facts for editorial purposes.

            If one article contains multiple genuinely independent factual
            developments, return them separately.

            The same supporting_news_id may appear in multiple developments only
            when that single article genuinely provides evidence for multiple
            independent events.

            Do not combine unrelated facts merely because they appear in the same
            article.

            GROUPING ARTICLES

            Multiple articles should be grouped when they describe the same
            underlying real-world event or continuing event.

            Group articles when:
            - different publishers report the same event;
            - one article provides additional details about the same transaction
              or event;
            - one article reports another stage or detail that still belongs to
              the same underlying event within this briefing window.

            For example:

            "Contoh Telecom agrees to acquire Sample Digital"
            "Contoh Telecom reveals the value of the Sample Digital acquisition"

            may belong to one development:
            "Contoh Telecom acquisition of Sample Digital"

            Do NOT group articles merely because:
            - they mention the same company;
            - they use the same ticker;
            - they belong to the same sector;
            - they discuss the same broad theme;
            - they were published close together.

            For example:

            "Contoh Telecom agrees to acquire Sample Digital"
            "Contoh Telecom reports H1 earnings"

            are separate developments.

            Be conservative when grouping. When two events are genuinely
            independent, keep them separate.

            ARTICLE EDITORIAL FRAMING

            Do not preserve an article's editorial bundle as the development.

            Extract the underlying factual event.

            For example, an article may contain:
            - an earnings result;
            - recent share-price performance;
            - foreign investor activity;
            - an analyst recommendation.

            If the only actual new company-state change is the earnings result,
            return the earnings development and ignore the surrounding market
            commentary.

            DEVELOPMENT TITLES

            Titles must describe the factual event itself.

            Good:
            "Contoh Telecom reports H1 2026 revenue up 4.1% YoY"

            Bad:
            "Contoh Telecom on track to exceed full-year targets"

            Bad:
            "Analysts bullish on Contoh Telecom after strong results"

            Do not place predictions, interpretations, recommendations, or
            unsupported conclusions in development titles.

            TICKERS

            Include a ticker only when the listed company itself is a subject of
            the development or its factual state is directly changed by the event.

            Do NOT include a ticker merely because:
            - an executive previously worked at that company;
            - the company is mentioned as background;
            - it is used as a peer or comparison;
            - an analyst or institution discussing the development is affiliated
              with it;
            - it is mentioned incidentally;
            - it is a customer or supplier without being directly affected by the
              event.

            For example:

            "Bank Alfa appoints executives previously employed by Bank Beta and
            Bank Gamma"

            should normally contain:
            [{subject_ticker}]

            not:
            [{subject_ticker}, {incidental_tickers}]

            EXCLUSION

            Exclude an article only when no valid factual development can be
            extracted from it.

            If part of an article is irrelevant but another part contains a valid
            development, extract the valid development and do not put that news ID
            in excluded_news_ids.

            Do NOT exclude a factual development simply because it appears minor.
            Materiality is handled by a later stage.

            Every input news ID must appear either in at least one development's
            supporting_news_ids or in excluded_news_ids, never in both.

            CURRENT DEVELOPMENT VS BACKGROUND

            Identify the factual development that is newly reported in the
            supplied article.

            Do not treat an older event, policy change, transaction, financial
            result, ownership change, or other historical fact as a new development
            merely because it is mentioned in a newly published article.

            Historical information may be retained only as supporting context for
            the new development.

            If the article contains only historical background, commentary, or a
            recap and does not report a new factual development, exclude it.

            Use the article's publication time only as evidence that the article is
            new. It does not imply that every event described in the article is
            new.

            ACCURACY

            Use only information supplied in the input articles.

            Never invent or estimate:
            - news IDs;
            - tickers;
            - companies;
            - dates;
            - amounts;
            - percentages;
            - transaction values;
            - causes;
            - consequences.

            Keep every figure, unit, date, and approximation marker exactly as
            supplied. Never round. Keep hedges such as "planned", "expected",
            "proposed", "about", and "reportedly" as supplied.

            {market_rules}

            When an article states relative timing (for example "next month" or
            "on Friday"), resolve it to an absolute date or month using that
            article's publication date, only when the publication date is supplied.
            Otherwise keep the relative wording exactly as written.

            If multiple sources describing the same development contain conflicting
            facts, do not silently choose one version. State the conflict
            neutrally.

            Do not convert predictions or commentary into factual claims.

            Every development must be traceable to at least one supporting_news_id
            from the input.

            The output must follow the provided structured response schema exactly.
            """
        )

        return template.format(
            market=context.market,
            insolvency_terms=terms.insolvency_terms,
            subject_ticker=terms.subject_ticker,
            incidental_tickers=terms.incidental_tickers,
            market_rules=context.market_rules,
        )

    @staticmethod
    def get_user_development_prompt():
        return inspect.cleandoc(
            """
            Extract distinct factual developments from the following equity-market
            news articles.

            For each article:
            - determine whether it contains zero, one, or multiple factual
              developments;
            - ignore recommendations, technical analysis, price commentary,
              investor-flow commentary, forecasts, and other editorial material
              unless they contain a separate concrete factual event;
            - group articles only when they describe the same underlying
              real-world event;
            - keep independent events separate;
            - include only tickers directly involved in each development;
            - preserve supporting news IDs for traceability.

            Do not judge whether a valid development is important.

            NEWS ARTICLES:
            {news_articles}

            Return the response in the following JSON schema:
            {format_instructions}
            """
        )