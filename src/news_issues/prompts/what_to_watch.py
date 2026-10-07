from dataclasses import dataclass
from datetime import date

from pydantic import BaseModel, Field

import inspect


WATCH_MARKET_STYLE = {
    "IDX": inspect.cleandoc(
        """
        Name each company by its ticker without the ".JK" suffix, for example
        ASII, not Astra International and not ASII.JK.

        For a dividend, the date to use is the cum-dividend date in the regular
        market, which is the last day to buy and still receive it. Do not make
        items for the ex-dividend, record, or payment dates.
        """
    ),
    "SGX": inspect.cleandoc(
        """
        Name each company by the short company name used in the development,
        for example DBS or Singtel. Do not use the SGX trading code, because
        readers do not recognise the codes.

        For a dividend, or a distribution by a REIT or business trust, the
        date to use is the ex-date, which is the first day the shares or units
        trade without it. Do not make items for the record or payment dates.
        """
    ),
}


WATCH_ILLUSTRATIONS = {
    "IDX": inspect.cleandoc(
        """
        Too long, repeats the date, and stacks several facts:
        timing_label: "12 October 2026"
        title: "PT Contoh Tbk (ABCD) will enter its cum-dividend date on 12
        October 2026 for the Rp150 per share interim dividend totalling Rp1.2
        trillion, with payment on 30 October."

        Correct:
        sort_date: "2026-10-12"
        timing_label: "12 Oct"
        title: "ABCD cum-dividend (regular market) for its Rp150 interim dividend"

        Correct, for an event that opens on a day and runs for a period:
        sort_date: "2026-10-05"
        timing_label: "5 Oct"
        title: "ABCD tender offer for WXYZ opens at Rp500 a share, until 3 Nov"

        Correct, when the development states only the month:
        sort_date: "2026-11-30"
        timing_label: "Nov"
        title: "ABCD shareholders vote on its Rp4.2 trillion purchase of PT Sample"
        """
    ),
    "SGX": inspect.cleandoc(
        """
        Too long, repeats the date, and stacks several facts:
        timing_label: "12 October 2026"
        title: "Contoh Holdings Ltd (XYZ) shares will trade ex-dividend on 12
        October 2026 for the S$0.05 per share interim dividend, with the record
        date on 13 October and payment on 30 October."

        Correct:
        sort_date: "2026-10-12"
        timing_label: "12 Oct"
        title: "Contoh Holdings trades ex-dividend for its S$0.05 interim dividend"

        Correct, for an event that opens on a day and runs for a period:
        sort_date: "2026-10-05"
        timing_label: "5 Oct"
        title: "Contoh Holdings offer for Sample Ltd opens at S$1.20 a share, until 3 Nov"

        Correct, when the development states only the month:
        sort_date: "2026-11-30"
        timing_label: "Nov"
        title: "Contoh Holdings shareholders vote on its S$420 million purchase of Sample Pte Ltd"
        """
    ),
}


WATCH_ISSUE_CADENCE = {
    "IDX": {
        "cadence": "daily",
        "this_issue": "today's",
        "quiet_period": "on a day with little news",
    },
    "SGX": {
        "cadence": "weekly",
        "this_issue": "this week's",
        "quiet_period": "in a week with little news",
    },
}


@dataclass(frozen=True)
class MarketContext:
    market: str
    unit_example: str
    market_rules: str


MARKET_CONTEXTS = {
    "IDX": MarketContext(
        market="Indonesian",
        unit_example='"Rp456 billion" to "Rp456B"',
        market_rules=(
            "Keep every currency exactly as supplied. Never convert between Rp "
            "and US$."
        ),
    ),
    "SGX": MarketContext(
        market="Singapore",
        unit_example='"S$456 million" to "S$456M"',
        market_rules=(
            "SGX issuers report in S$, US$, RMB, and other currencies. Keep every "
            "currency exactly as supplied, never convert, and always keep the full "
            'prefix ("S$", "US$"), never a bare "$". For REITs and business '
            "trusts, keep per-unit metrics (DPU, NAV per unit) and terms such as "
            '"unitholders" as supplied. Never restate them as per-share.'
        ),
    ),
}


class WhatToWatchItem(BaseModel):
    development_ids: list[str] = Field(
        min_length=1,
        description=(
            "Development IDs this item is taken from, exactly as supplied. "
            "Usually one. Use more than one only when several developments "
            "state the same event on the same date."
        ),
    )

    sort_date: date = Field(
        description=(
            "The calendar day the event falls on, as YYYY-MM-DD. For an event "
            "that opens and runs for a period, the opening day. For a month or "
            "quarter, its last day. For a deadline, the deadline day. Must be "
            "after AS OF."
        )
    )

    timing_label: str = Field(
        description=(
            "Short display form of the same timing: '5 Oct' for a day, 'Nov' "
            "for a month, 'Q4' for a quarter, 'By 31 Dec' for a deadline. Add "
            "the year only when it differs from the AS OF year, for example "
            "'12 Jan 2027'. Never more precise than the development states."
        )
    )

    title: str = Field(
        description=(
            "One line of at most 14 words saying what happens on that date. "
            "Starts with the company, or with the regulator or market for a "
            "market-wide event. At most one figure. May end with the closing "
            "day of a period, such as 'until 3 Nov'. Does not repeat the date "
            "in timing_label. No full stop at the end."
        )
    )


class WhatToWatch(BaseModel):
    explanation: str = Field(
        description=(
            "Written before items. Brief selection notes: which developments "
            "state a qualifying upcoming event, which dated events were "
            "rejected and why, and why the selected ones matter most. Refer to "
            "Development IDs. If nothing qualifies, say so. Use only supplied "
            "facts."
        )
    )

    items: list[WhatToWatchItem] = Field(
        default_factory=list,
        max_length=5,
        description=(
            "At most 5 upcoming events, ordered by sort_date, earliest first. "
            "Empty list when none qualify."
        ),
    )


class WhatToWatchPrompts:
    @staticmethod
    def get_system_prompt(exchange: str):
        context = MARKET_CONTEXTS[exchange]
        market_style = WATCH_MARKET_STYLE[exchange]
        illustration = WATCH_ILLUSTRATIONS[exchange]
        issue_cadence = WATCH_ISSUE_CADENCE[exchange]

        template = inspect.cleandoc(
            """
            You are an editor for the {cadence} news issue of the {market} equity
            market.

            You receive the developments in {this_issue} issue. Each development has
            a Development ID, an event label naming what the story is about, a
            factual summary, and its tickers.

            Your only task is to produce the What to Watch list: a short
            calendar of upcoming events taken from those developments. It is
            shown in a narrow sidebar as rows of a date and one line of text,
            so every word must earn its place.

            WHAT QUALIFIES

            An item is one upcoming event. It qualifies only when ALL of the
            following are true:

            1. The summary explicitly states the event and when it happens.
            2. The event falls after AS OF. An event on the AS OF day itself
               does not qualify.
            3. Something happens on that day that an investor in {market}
               equities can act on or that changes the situation. Examples: a shareholder vote,
               an offer or subscription period opening, the last day to qualify
               for a dividend or rights, a listing or delisting, a rule or
               policy taking effect, a scheduled decision or ruling, a deadline
               that decides whether a deal proceeds.

            Do not include:
            - a date that has already passed, even if the summary presents it
              as upcoming;
            - a target or expected completion period with no decision attached
              to it, such as "completion is targeted for the first quarter";
            - a date on which nothing changes for an investor, such as a record
              date or a payment date;
            - anything you would have to infer. Do not invent the next step of
              a development.

            One development may give at most two items, and only when they are
            two different events, such as an offering opening and the
            securities listing. Do not make two items for two steps of the same
            mechanism. Do not make two items for the same event, even when
            several developments report it: make one item and list every
            Development ID. Do not combine unrelated companies or events in
            one item.

            MARKET

            {market_rules}

            {market_style}

            TIMING

            Timing must be stated in the summary. Do not infer, estimate, or
            shift dates.

            When the summary gives a day and month without a year for an event
            it presents as upcoming, use the first such day after AS OF.
            Resolve relative timing such as "next week" only when the summary
            gives the date it is relative to. If the timing cannot be resolved
            to a day, month, quarter, or deadline, drop the item.

            Be only as precise as the summary. If it says the vote is in
            November, the timing is the month, not a day.

            SELECTION

            Return at most 5 items. Five is a ceiling, not a target. One or
            zero items is a valid result, and {quiet_period} it is
            the expected result. Do not lower the bar to fill the list.

            When more than five events qualify, keep the ones that matter most
            to an investor in {market} equities, judged from the facts in the
            summary: the
            size of the transaction or payout, how many investors it affects,
            and whether it applies to the whole market. Between events of
            similar weight, keep the nearer one.

            Write the explanation field first and make the selection there.
            Then write items consistent with it, ordered by sort_date, earliest
            first.

            WRITING THE ITEM

            development_ids: The Development IDs the event comes from, copied
            exactly. Tickers and source articles are attached from these IDs
            afterwards, so do not write tickers as a separate list.

            sort_date: The calendar day of the event. For an event that opens
            and runs for a period, the opening day. For a month or quarter, its
            last day. For a deadline, the deadline day.

            timing_label: The short display form of the same timing. Add the
            year only when it differs from the AS OF year.

            title: One line of at most 14 words saying what happens on that
            date. Start with the company, or with the regulator or market when
            the event is market-wide. Use at most one figure, the one that
            shows the size. When the event runs for a period, the title may end
            with its closing day. Do not repeat the date that is in
            timing_label, do not explain why it matters, and do not end with a
            full stop.

            FORMAT ILLUSTRATION (fictional companies, do not reuse their facts)

            {illustration}

            Use only facts contained in the supplied developments. Write in
            natural English. Follow the provided response schema exactly.
            """
        )

        return template.format(
            market=context.market,
            market_rules=context.market_rules,
            market_style=market_style,
            illustration=illustration,
            cadence=issue_cadence["cadence"],
            this_issue=issue_cadence["this_issue"],
            quiet_period=issue_cadence["quiet_period"],
        )

    @staticmethod
    def get_user_prompt():
        return inspect.cleandoc(
            """
            Produce What to Watch from the developments below.

            AS OF:
            {as_of}

            DEVELOPMENTS:
            {developments}

            Return the response in the following JSON schema:
            {format_instructions}
            """
        )