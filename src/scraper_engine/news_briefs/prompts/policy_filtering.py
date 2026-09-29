from dataclasses import dataclass
from pydantic import BaseModel, Field

from .market_context import MARKET_CONTEXTS

import inspect


@dataclass(frozen=True)
class PolicyAuthorities:
    authorities: str
    exchange_rule_examples: str


POLICY_AUTHORITIES = {
    "IDX": PolicyAuthorities(
        authorities=(
            "the Indonesian government, a ministry, Bank Indonesia, OJK, the IDX, "
            "KSEI, the House of Representatives, or a court"
        ),
        exchange_rule_examples=(
            "trading rules, listing rules, price limits, special monitoring, index "
            "or free-float rules set by the exchange"
        ),
    ),
    "SGX": PolicyAuthorities(
        authorities=(
            "the Singapore government, a ministry, the Monetary Authority of "
            "Singapore (MAS), SGX or SGX RegCo, CDP, Parliament, or a court"
        ),
        exchange_rule_examples=(
            "trading rules, listing rules, price limits, free-float or "
            "shareholding-spread requirements, board lot rules, index rules set by "
            "the exchange"
        ),
    ),
}


class SelectedPolicySchema(BaseModel):
    id: int = Field(
        description="ID of the selected article from the input records."
    )

    title: str = Field(
        description=(
            "One sentence, ideally under 20 words, preserving the policy action "
            "and scope. Use a familiar short company name or ticker instead of a "
            "full legal name. Describe the action relative to BRIEF AS OF."
        )
    )


class PolicyFilterSchema(BaseModel):
    explanation: str = Field(
        description=(
            "Written before selected policies. For each selected article, state the "
            "issuing authority, the action, whether it is enacted or proposed, and "
            "its scope. Briefly note notable rejections and why, citing article IDs."
        )
    )

    selected_policies: list[SelectedPolicySchema] = Field(
        description=(
            "Up to three selected articles, most important first. Include each "
            "article ID and a display title. Empty list when none qualify."
        )
    )


class PolicyFilterPrompts:
    @staticmethod
    def get_system_prompt(exchange: str):
        context = MARKET_CONTEXTS[exchange]
        policy = POLICY_AUTHORITIES[exchange]

        template = inspect.cleandoc(
            """
            You select the most important policy and regulation news for a
            {market} equity-market brief.

            Every input article already carries a policy-related tag. Tags are
            applied automatically and are often wrong or loose, so judge each
            article on its content, not its tag.

            QUALIFYING ARTICLES

            An article qualifies only when it reports a concrete action by a
            public authority: {authorities}. The action must be one of:
            - a rate, reserve, or monetary-operation decision;
            - a new, amended, or revoked regulation, rule, or law;
            - a tax, tariff, royalty, levy, subsidy, quota, or export or import
              policy;
            - an exchange or market-structure rule ({exchange_rule_examples});
            - an enforcement action or sanction with market-wide or sector-wide
              significance;
            - a formally published draft regulation or bill with a stated
              timeline.

            Exclude:
            - a single company's routine compliance, filings, disclosures, or
              responses to exchange queries;
            - political news, statements, or opinions with no concrete policy
              action;
            - company news that mentions a policy only as background;
            - commentary, analyst views, or previews of a decision that has not
              been made, unless a formal draft or timeline is reported;
            - index rebalancing by private index providers.

            RANKING

            Rank qualifying articles by these criteria, in order:
            1. Status: enacted or taking effect ranks above formally proposed.
               Discussed or rumored does not qualify.
            2. Scope: the whole market, then a whole sector, then a named group of
               listed companies, then a single listed company.
            3. Change: a new rule or a reversal ranks above an extension or minor
               amendment of an existing one.
            4. Directness: rules that change what listed companies or investors can
               do, pay, or earn rank above indirect macro effects.

            DEDUPLICATION

            Select at most one article per policy action. When several articles
            cover the same action, select the one that states the action and its
            terms most completely. Different actions by the same authority on the
            same day are separate policy actions.

            MARKET

            {market_rules}

            TENSE

            Judge status relative to BRIEF AS OF. An action effective on or after
            BRIEF AS OF is described as scheduled or taking effect, not as
            completed.

            OUTPUT

            Write the explanation first, then return up to three selected
            articles, most important first. Three is a ceiling, not a target.
            Return an empty list when none qualify. Use only IDs that appear in
            the input.

            For each selected article, write a display title of one sentence,
            ideally under 20 words, that preserves the policy action and its
            scope. Do not copy long legal company names or list every affected
            issuer. Use a familiar short name, ticker, or issuer count instead.
            Do not add facts that are absent from the article.
            """
        )

        return template.format(
            market=context.market,
            authorities=policy.authorities,
            exchange_rule_examples=policy.exchange_rule_examples,
            market_rules=context.market_rules,
        )

    @staticmethod
    def get_user_prompt():
        return inspect.cleandoc(
            """
            Select the most important qualifying policy articles from these news
            records.

            BRIEF AS OF:
            {brief_as_of}

            NEWS ARTICLES:
            {news_articles}

            Return the response in the following JSON schema:
            {format_instructions}
            """
        )