from typing import Literal
from pydantic import BaseModel, Field

from .market_context import MARKET_CONTEXTS

import inspect


WATCH_ILLUSTRATIONS = {
    "IDX": inspect.cleandoc(
        """
        Too long and repetitive:
        context: "PT Contoh Tbk (ABCD) will hold an EGMS to vote on its
        proposed acquisition of PT Sample, a deal valued at Rp4.2 trillion,
        which represents 61% of ABCD's equity and therefore requires
        shareholder approval under OJK rules, while the company has also
        stated that financing will come from a combination of bank loans and
        internal cash."
        watch_for: "Whether shareholders approve the large Rp4.2 trillion
        acquisition that requires their approval."

        Correct:
        context: "The Rp4.2 trillion acquisition of PT Sample equals 61% of
        ABCD's equity and requires shareholder approval."
        watch_for: "Whether shareholders approve the deal and on what
        financing terms."
        """
    ),
    "SGX": inspect.cleandoc(
        """
        Too long and repetitive:
        context: "Contoh Holdings Ltd (XYZ) will hold an EGM to vote on its
        proposed acquisition of Sample Pte Ltd, a deal valued at S$420
        million, which is a major transaction under SGX listing rules and
        therefore requires shareholder approval, while the company has also
        stated that financing will come from a combination of bank loans and
        internal cash."
        watch_for: "Whether shareholders approve the large S$420 million
        acquisition that requires their approval."

        Correct:
        context: "The S$420 million acquisition of Sample Pte Ltd is a major
        transaction under SGX listing rules and requires shareholder approval."
        watch_for: "Whether shareholders approve the deal and on what
        financing terms."
        """
    ),
}


class WhatToWatchItem(BaseModel):
    title: str = Field(
        description=(
            "Headline under 10 words naming the catalyst and the company involved, "
            "or the regulator or market when the catalyst is market-wide."
        )
    )

    timing_label: str = Field(
        description=(
            "Display text matching timing_type: '22 Sep 2026' for date, 'Oct 2026' "
            "for month, 'Q4 2026' for quarter, 'By end-2026' or '22-26 Sep 2026' "
            "for window. Use only timing stated in the supplied developments."
        )
    )

    timing_type: Literal["date", "month", "quarter", "window"] = Field(
        description=(
            "date: a single specific day. month: a whole named month. quarter: a "
            "named quarter. window: any other span or deadline."
        )
    )

    context: str = Field(
        description=(
            "Exactly one sentence, ideally under 25 words, stating what is changing "
            "and the single most important supplied figure, currency prefix kept "
            "as supplied. No semicolons. Do not restate the title."
        )
    )

    watch_for: str = Field(
        description=(
            "One sentence, ideally under 20 words, starting with 'Whether' or "
            "'How', naming only the unresolved question the event will answer, "
            "phrased neutrally. Must not restate any fact from the title or context."
        )
    )

    symbols: list[str] = Field(
        description=(
            "Tickers exactly as supplied with the supporting developments. Empty "
            "list when none apply."
        )
    )


class WhatToWatch(BaseModel):
    explanation: str = Field(
        description=(
            "Written before items. Brief selection rationale: which developments "
            "contain a qualifying future catalyst, which were rejected and why, and "
            "why the selected ones are the most material. Refer to Development IDs. "
            "If no catalyst qualifies, explain why. Use only supplied facts."
        )
    )

    items: list[WhatToWatchItem] = Field(
        default_factory=list,
        description=(
            "At most 3 qualifying catalysts, ordered chronologically, earliest "
            "first. Empty list when none qualify."
        ),
    )


class WhatToWatchPrompts:
    @staticmethod
    def get_system_prompt(exchange: str):
        context = MARKET_CONTEXTS[exchange]
        illustration = WATCH_ILLUSTRATIONS[exchange]

        template = inspect.cleandoc(
            """
            You are an editor for a {market} equity-market intelligence product.

            You receive canonical factual developments that have already been
            extracted, validated, deduplicated, and reconciled against recent briefs.
            Each development has a Development ID.

            Your only task is to produce a small, high-signal What to Watch list,
            displayed as compact cards in a narrow mobile-width carousel. Every word
            must earn its place.

            QUALIFYING CATALYSTS

            A catalyst qualifies only when ALL of the following are true:

            1. The supplied development explicitly establishes a future event,
               decision, deadline, meeting, vote, ruling, approval, payment,
               condition, or other identifiable trigger.
            2. The catalyst occurs after BRIEF AS OF. A catalyst on the same
               calendar day qualifies only if the supplied facts show it has not
               yet occurred at that time.
            3. Something material remains unresolved, or the occurrence of the
               event itself would materially change the known state.
            4. The outcome would likely constitute a materially new development
               for a {market} equity-market participant.

            Do not include an item merely because something is planned or
            proposed, a transaction has not yet completed, implementation is
            expected in the future, a target completion period is mentioned, or a
            routine corporate action has a future date.

            Do not invent the next step of a development. Do not combine unrelated
            companies or events into one item. Do not create two items for the same
            catalyst.

            MARKET

            {market_rules}

            TIMING

            Timing must be explicitly supported by the supplied developments. Do
            not infer, estimate, or shift dates. Drop any catalyst whose timing has
            already passed relative to BRIEF AS OF, even if the development
            presents it as upcoming.

            Resolve relative timing (for example "next month") against the
            development's own date, and only when that date is supplied. If timing
            cannot be resolved to a date, month, quarter, or window, drop the item.

            Do not present an expected or targeted period as a firm date. A target
            period is a window or month, not a date.

            SELECTION

            Return at most 3 items. Three is a ceiling, not a target. One or zero
            items is a valid result.

            When several catalysts qualify, prioritize:
            1. materiality of the potential state change;
            2. relevance to listed {market} equities or the overall market;
            3. imminence.

            Write the explanation field first and make the selection there. Then
            write items consistent with it, ordered chronologically, earliest first.

            WRITING THE ITEM

            Each field has one job. No fact may appear in more than one field.

            title: What the catalyst is, under 10 words. Name the company, or the
            regulator or market when the catalyst is market-wide.

            context: Exactly one sentence, ideally under 25 words, stating what is
            changing and the single most important supplied figure showing why it
            matters (size, stake, deadline, required approval). Pick one figure;
            do not list several. No semicolons, and do not chain clauses with
            "while", "including", or "with" to fit more facts in.

            watch_for: One sentence, ideally under 20 words, naming only the
            unresolved variable, starting with "Whether" or "How". It must not
            restate any fact from the title or context. Phrase it neutrally and do
            not imply an expected outcome.

            symbols: Only tickers explicitly supplied with the supporting
            developments. Do not infer, construct, or modify tickers.

            FORMAT ILLUSTRATION (fictional company, do not reuse its facts)

            {illustration}

            Use only facts contained in the supplied developments. Write in natural
            English with proper punctuation. Follow the provided response schema
            exactly.
            """
        )

        return template.format(
            market=context.market,
            market_rules=context.market_rules,
            illustration=illustration,
        )

    @staticmethod
    def get_user_prompt():
        return inspect.cleandoc(
            """
            Produce What to Watch from the following canonical developments.

            BRIEF AS OF:
            {brief_as_of}

            DEVELOPMENTS:
            {developments}

            Return the response in the following JSON schema:
            {format_instructions}
            """
        )