from pydantic import BaseModel, Field

from .market_context import MARKET_CONTEXTS

import inspect


REGULATOR_EXAMPLES = {
    "IDX": {
        "topic": '"Bank Indonesia SRBI policy changes"',
        "too_broad": '"Bank Indonesia"',
    },
    "SGX": {
        "topic": '"MAS S$NEER policy band changes"',
        "too_broad": '"MAS"',
    },
}


class DevelopmentTopic(BaseModel):
    topic: str = Field(
        description=(
            "Concise name of the specific underlying market development or event."
        )
    )

    known_state: str = Field(
        description=(
            "Concise cumulative factual state already established about the topic "
            "from the supplied developments."
        )
    )


class DevelopmentTopics(BaseModel):
    topics: list[DevelopmentTopic]


class DevelopmentTopicsPrompts:
    @staticmethod
    def get_system_development_topics(exchange: str):
        context = MARKET_CONTEXTS[exchange]
        regulator = REGULATOR_EXAMPLES[exchange]

        template = inspect.cleandoc(
            """
            You normalize {market} market-news developments into a compact list of
            known topic states.

            The input contains news developments represented only by a title and
            summary. Some developments may describe the same underlying event using
            different wording or additional details.

            Your task is to consolidate developments that belong to the same
            underlying event and return one topic with its cumulative known state.

            A topic represents one specific underlying development, not merely a
            company, ticker, industry, or broad category.

            Examples below use fictional companies. Do not reuse their facts.

            Examples of good topics:
            - "Contoh Construction bond payment distress and trading suspension"
            - "Sample Retail IPO"
            - "Contoh Media sale of Sample Studios"
            - {regulator_topic}

            Examples that are too broad:
            - "Contoh Construction"
            - {regulator_too_broad}
            - "IPO"
            - "Earnings"
            - "Corporate actions"

            CONSOLIDATION RULES

            1. Merge developments when they describe the same underlying event or
               ongoing situation, even when the wording differs.

            2. When several developments belong to the same topic, combine their
               factual information into one known_state.

            3. Do not merge developments merely because they involve the same
               company or institution.

               Example:
               - "Contoh Infrastructure secures new contracts"
               - "Contoh Infrastructure plans asset divestment"

               These are separate topics.

            4. A later consequence may belong to the same topic when it directly
               advances the same underlying situation.

               Example:
               - a company misses a bond payment and trading is suspended;
               - a rating agency later downgrades the company because of that
                 missed payment.

               These can belong to the same evolving topic.

            5. Developments about different events must remain separate even when
               they share the same entity.

            6. Do not infer relationships or facts that are not supported by the
               supplied titles and summaries.

            TOPIC

            The topic must:
            - be concise;
            - identify the main entity, policy, transaction, program, or event;
            - describe the underlying development rather than copy an article
              headline;
            - be specific enough that a later development about the same event can
              be recognized as related.

            KNOWN STATE

            The known_state describes what is materially established about that
            topic from the supplied developments.

            It must:
            - be factual, usually one or two short sentences;
            - contain only the facts needed to recognize whether a later development
              materially changes the topic, such as actions, amounts, dates,
              ratings, status changes, or scheduled next events;
            - combine complementary information from duplicate developments;
            - avoid repeating the same fact;
            - contain no prediction, recommendation, market impact, or unsupported
              interpretation.

            FACTUAL ACCURACY

            Preserve every retained number, percentage, currency, unit, date, and
            rating exactly as supplied. Do not recalculate, round, or guess
            corrections.

            {market_rules}

            If supplied developments conflict, state the conflict clearly without
            choosing or inventing a replacement value.

            Return only final factual text in topic and known_state, with no
            drafting notes, self-corrections, or unrelated prefixes.

            Before returning, check every retained figure against the supplied
            developments.

            Every input development must be represented by exactly one output topic.

            Do not rank topics.
            Do not remove a topic because it appears unimportant.
            """
        )

        return template.format(
            market=context.market,
            regulator_topic=regulator["topic"],
            regulator_too_broad=regulator["too_broad"],
            market_rules=context.market_rules,
        )

    @staticmethod
    def get_user_development_topics():
        return inspect.cleandoc(
            """
            Convert the following developments into a compact list of known topic
            states. Consolidate developments that describe the same underlying
            event.

            DEVELOPMENTS:
            {developments}

            Return the response in the following JSON schema:
            {format_instructions}
            """
        )