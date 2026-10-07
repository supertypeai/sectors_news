from enum import Enum

from pydantic import BaseModel, Field


class Section(str, Enum):
    MARKET_STRUCTURE_POLICY = "market_structure_policy"
    MACRO_FLOWS = "macro_flows"
    DEALS_CONTROL = "deals_control"
    CAPITAL_RAISING_BUYBACKS = "capital_raising_buybacks"
    EARNINGS_GUIDANCE = "earnings_guidance"
    OTHER = "other"


class DevelopmentAssignment(BaseModel):
    development_id: str = Field(
        description="ID of one input development, copied exactly.",
    )
    covered_in_previous_issue: bool = Field(
        description=(
            "True when this development is the same story as one in the "
            "PREVIOUS ISSUE list. False otherwise, and always false when that "
            "list is empty."
        ),
    )
    section: Section = Field(
        description="The single section this development belongs to.",
    )
    importance: int = Field(
        ge=1,
        le=5,
        description=(
            "Importance to an equity investor in this market, from 1 to 5."
        ),
    )


class AssignmentResult(BaseModel):
    assignments: list[DevelopmentAssignment] = Field(
        description="Exactly one assignment for every input development.",
    )
    lead_development_id: str | None = Field(
        description=(
            "ID of the single most important development of the issue. It must "
            "be one of the developments with the highest importance score. "
            "Null only when the input is empty."
        ),
    )


ASSIGNMENT_MARKET_STYLE = {
    "IDX": {
        "audience": "Indonesian equity investors",
        "cadence": "daily",
        "this_issue": "today's",
        "read_period": "today",
        "lead_tie_breaks": (
            "1. The one whose event happened closest to the AS OF date.\n"
            "2. The one that affects the most investors, judged from the summary: a market-wide or sector-wide effect, or a company with a large market value or trading value.\n"
            "3. The one with the highest article_count."
        ),
        "policy_examples": (
            "OJK and IDX rules, trading mechanisms, price limits, index "
            "inclusions and removals, suspensions and delistings, sector "
            "regulation, tax changes, state-owned enterprise policy"
        ),
        "macro_examples": (
            "central bank decisions, the rupiah, bond yields, inflation and "
            "other data releases, commodity prices, the state budget, sovereign "
            "ratings, market-wide foreign fund flows"
        ),
        "deals_examples": (
            "acquisitions, divestments, mergers, tender offers, changes of "
            "control, share purchases and sales by controllers, insiders and "
            "major shareholders, affiliated-party transactions, joint ventures"
        ),
        "capital_examples": (
            "rights issues, private placements, IPOs, bond and sukuk issues, "
            "loan facilities, share buybacks"
        ),
        "earnings_description": (
            "Financial and operational results, company targets and guidance, "
            "and broker changes to estimates, target prices, or ratings."
        ),
        "threshold_top": "Rp10 trillion",
        "threshold_major": "Rp1 trillion",
        "threshold_notable": "Rp100 billion",
        "home_currency": "rupiah",
        "extra_major_rules": "",
        "price_move_rule": (
            "A listed company's shares at the upper or lower price limit for "
            "two or more sessions in a row, or a share price move of 25% or "
            "more within this news cycle."
        ),
        "top_executive": "chief executive or president director",
    },
    "SGX": {
        "audience": "Singapore equity investors",
        "cadence": "weekly",
        "this_issue": "this week's",
        "read_period": "this week",
        "lead_tie_breaks": (
            "1. The one that affects the most investors, judged from the summary: a market-wide or sector-wide effect, or a company with a large market value or trading value.\n"
            "2. The one with the highest article_count.\n"
            "3. The one whose event happened closest to the AS OF date."
        ),
        "policy_examples": (
            "MAS and SGX rules, listing rules, trading mechanisms, index "
            "inclusions and removals, suspensions and delistings, sector "
            "regulation, tax changes, property cooling measures and other "
            "property rules"
        ),
        "macro_examples": (
            "central bank decisions, the Singapore dollar, interest rates and "
            "bond yields, inflation and other data releases, commodity prices, "
            "the government Budget, official property price, rent, and sales "
            "data, market-wide fund flows"
        ),
        "deals_examples": (
            "acquisitions, divestments, mergers, general offers, "
            "privatisations, schemes of arrangement, changes of control, share "
            "purchases and sales by controlling and substantial shareholders "
            "and directors, interested person transactions, joint ventures, "
            "property purchases and sales by REITs and developers, land tender "
            "awards"
        ),
        "capital_examples": (
            "rights issues, placements, preferential offerings, IPOs, bond and "
            "note issues, loan facilities, share buybacks"
        ),
        "earnings_description": (
            "Financial and operational results, business updates, "
            "distributions per unit reported with results, company targets and "
            "guidance, and broker changes to estimates, target prices, or "
            "ratings."
        ),
        "threshold_top": "S$1 billion",
        "threshold_major": "S$100 million",
        "threshold_notable": "S$10 million",
        "home_currency": "Singapore dollar",
        "extra_major_rules": (
            "\n- A general offer or privatisation offer for a listed company."
        ),
        "price_move_rule": (
            "A share price move of 25% or more in a listed company within this "
            "news cycle."
        ),
        "top_executive": "chief executive",
    },
}


ASSIGNMENT_SYSTEM_PROMPT_TEMPLATE = """You are the managing editor of a {cadence} issue for {audience}. You receive every development collected for {this_issue} issue, an AS OF date, and the stories the previous issue already published. For each development you decide whether it was already covered, which section it belongs to, and how important it is. Then you pick the lead.

You do not write or rewrite any text. You only assign.

THE EVENT LABEL
Each development has an event label that names what the story is about. Its title may reflect one article's angle, such as an analyst's view of a deal. Decide the section and the score from the event the label names, and use the summary for the facts.

SECTIONS
Assign each development to exactly one section.

market_structure_policy
Decisions by regulators, the exchange, or the government that change how the market or a sector operates. Examples: {policy_examples}.

macro_flows
Economy-wide and market-wide conditions. Examples: {macro_examples}.

deals_control
Changes in who owns or controls a company or an asset. Examples: {deals_examples}.

capital_raising_buybacks
A company raising funding or buying back its own shares. Examples: {capital_examples}.

earnings_guidance
{earnings_description}

other
Anything that fits none of the above. Examples: dividends, management changes, lawsuits, contracts, expansion plans, company features.

WHEN A DEVELOPMENT FITS TWO SECTIONS
1. If the event is a rule or decision by a regulator, the exchange, or the government, use market_structure_policy, even when the article focuses on the companies affected.
2. Otherwise choose by what changes for shareholders, in this order: ownership or control (deals_control), then funding (capital_raising_buybacks), then results (earnings_guidance). A share issue that changes who controls the company is deals_control. An acquisition paid for with a share issue is deals_control.
3. Do not use other to avoid a decision. Use it only when no section fits.

IMPORTANCE
Score each development from 1 to 5 in two passes.

PASS 1: IS IT NEW?
Start with the PREVIOUS ISSUE list. It holds the stories the last issue published as its lead or as a section story.
- A development is previously covered when it is the same story as one in that list: the same company or institution and the same situation. Sharing only a company or a theme is not a match.
- Set covered_in_previous_issue to true for a previously covered development and false for every other one. If the list is empty, nothing is previously covered.

A previously covered development is new only when the story has moved on since: a new decision, a completed step, a newly released figure, or a further price move. The headline and blurb show what readers were already told. A fact that already appears there is not a new step. Repeat coverage, added analyst comment, and clarifications that change nothing are not new.

A development that was not previously covered is new when the articles report its subject as news: a decision, transaction, filing, data release, market move, or announcement. It is still new when the decision behind it was signed or took effect earlier, as long as the articles treat it as news now, for example with first reports or a price reaction.

These are not new, whether or not they were covered before:
- A feature, interview, profile, or company explanation that announces no decision, no transaction, and no newly released figure.
- An explainer or opinion piece about a rule or deal that the articles do not report as news.
- Financial results quoted as background in a piece about strategy, outlook, or explanation. Results are new only when their release is itself the event.
- A periodic recap of market data, such as daily or weekly index moves, fund flows, or most-traded lists, unless the summary states a record or a multi-year extreme.

A development that is not new scores 1 or 2, whatever its size.

PASS 2: HOW BIG IS IT?
Apply this only to developments that are new. Judge size from the amounts stated in the summary. If more than one line applies, use the highest level that applies.

5: Changes conditions for the whole market or an entire sector now. Only these qualify:
- A decision by a regulator, the exchange, the government, or the central bank that was first reported or took effect in this news cycle and applies market-wide or sector-wide.
- A macro or market move that the summary describes as a record or a multi-year extreme.
- A transaction, default, or fraud case of {threshold_top} or more.
Most days have no 5.

4: Major for one company, or a clear signal for a sector. Any of these:
- A change of control of a listed company.{extra_major_rules}
- A transaction, fundraising, buyback, or debt event of {threshold_major} or more.
- A proposed or draft rule for a sector that has not yet taken effect.
- A central bank decision or data release that the summary says differed from expectations.
- A default, suspension, delisting, or major legal or regulatory action against a listed company.
- Newly released results that show a swing between profit and loss, or a raised or cut company guidance.
- {price_move_rule}

3: Notable for holders of that stock. Any of these:
- A transaction, fundraising, buyback, or contract of {threshold_notable} to under {threshold_major}.
- Newly released results or guidance without the extremes listed under 4.
- A broker changing a rating, target price, or estimate.
- A change of {top_executive}.
- A dividend that is special or clearly different from the previous period.
- A central bank decision or data release in line with expectations.

2: Small or routine. Any of these:
- A value under {threshold_notable}.
- A shareholder trade that does not change control and has no larger stated value.
- A recurring corporate action in line with previous periods, such as a regular dividend.
- A development that is not new but still carries a figure a reader may want.

1: Nothing an investor would act on.

For amounts in another currency, judge by their rough {home_currency} equivalent. When no amount is stated, use the line that describes the event best.

article_count shows how many outlets covered the development. Treat it as a weak sign of attention. Never raise a score on coverage alone.

Do not raise scores to fill a section: a section with nothing important is left empty.

LEAD
The lead is the one development an investor most needs to read {read_period}. It must be an event, not an explainer, and it must be among the developments with the highest importance score. Any section qualifies, including other.

When several developments share the highest score, choose in this order:
{lead_tie_breaks}

OUTPUT RULES
- Return exactly one assignment for every input development ID.
- Use only IDs that appear in the input. Never invent an ID."""


def get_assignment_system_prompt(exchange: str):
    market_style = ASSIGNMENT_MARKET_STYLE[exchange]
    return ASSIGNMENT_SYSTEM_PROMPT_TEMPLATE.format(
        audience=market_style["audience"],
        cadence=market_style["cadence"],
        this_issue=market_style["this_issue"],
        read_period=market_style["read_period"],
        lead_tie_breaks=market_style["lead_tie_breaks"],
        policy_examples=market_style["policy_examples"],
        macro_examples=market_style["macro_examples"],
        deals_examples=market_style["deals_examples"],
        capital_examples=market_style["capital_examples"],
        earnings_description=market_style["earnings_description"],
        threshold_top=market_style["threshold_top"],
        threshold_major=market_style["threshold_major"],
        threshold_notable=market_style["threshold_notable"],
        home_currency=market_style["home_currency"],
        extra_major_rules=market_style["extra_major_rules"],
        price_move_rule=market_style["price_move_rule"],
        top_executive=market_style["top_executive"],
    )


ASSIGNMENT_USER_PROMPT = """Assign a section and an importance score to every development below, then pick the lead.

AS OF: {as_of}

PREVIOUS ISSUE:
Each story has an event label, a headline, a blurb, and its tickers. An empty list means there is no previous issue.
{previous_stories}

DEVELOPMENTS:
Each development has an id, an event label, a title, a summary, its tickers, and an article_count.
{developments}

Return the response in the following JSON schema:
{format_instructions}"""