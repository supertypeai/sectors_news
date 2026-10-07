from enum import Enum

from pydantic import BaseModel, Field


class Slot(str, Enum):
    LEAD = "lead"
    STORY = "story"
    FLASH = "flash"


class DisplayCopy(BaseModel):
    headline: str = Field(
        description=(
            "One line stating what happened, with the single most important "
            "figure. No full stop at the end."
        ),
    )
    blurb: str | None = Field(
        description=(
            "For slot lead: one paragraph of up to 4 sentences. For slot story: "
            "up to 3 sentences. For slot flash: null. Also null when the "
            "development has nothing to add beyond the headline."
        ),
    )


DISPLAY_MARKET_STYLE = {
    "IDX": {
        "audience": "Indonesian equity investors",
        "cadence": "daily",
        "names_and_terms": """- In the headline, name a listed company by its ticker without the exchange suffix, for example "KIJA". Use only tickers given with the development.
- In the blurb, use the company's short common name on first mention, for example "Jababeka". Never write "PT" or "Tbk".
- Name unlisted companies by their short name without "PT". Describe an obscure entity by what it is, for example "a Kendal industrial estate developer", when the name alone tells the reader nothing.
- Write "lower price limit" for auto rejection bottom (ARB) and "upper price limit" for auto rejection top (ARA). Use "price floor" only for the minimum share price rule.""",
        "number_rules": """- Round large rupiah amounts and share counts to at most two decimals with the unit written out: Rp340,863,090,000 becomes "Rp340.9 billion", and 2,620,000,000 shares becomes "2.62 billion shares".
- Keep per-share prices, percentages, and ratios exactly as given.""",
    },
    "SGX": {
        "audience": "Singapore equity investors",
        "cadence": "weekly",
        "names_and_terms": """- In the headline and the blurb, name a listed company by its short common name, for example "DBS" or "CapitaLand Investment". Never use the SGX trading code, because readers do not recognise the codes. Name only companies that appear in the development.
- Never write "Ltd", "Limited", or "Pte".
- Name unlisted companies by their short name without "Pte Ltd". Describe an obscure entity by what it is, for example "a Johor data centre developer", when the name alone tells the reader nothing.
- For REITs and business trusts, keep "units", "unitholders", and "distribution per unit" as the development gives them. Never restate them as shares or per-share figures.""",
        "number_rules": """- Round large amounts and share or unit counts to at most two decimals with the unit written out: S$340,863,090 becomes "S$340.9 million", and 2,620,000,000 units becomes "2.62 billion units".
- Keep the full currency prefix the development gives, such as "S$", "US$", or "RMB". Never write a bare "$" and never convert between currencies.
- Keep per-share and per-unit prices, percentages, and ratios exactly as given.""",
    },
}


DISPLAY_SYSTEM_PROMPT_TEMPLATE = """
You write the copy for the homepage of a {cadence} issue for {audience}. You receive one development, which is a complete factual record of one story, and the slot it will fill. You turn it into short copy that a reader can take in at a glance.

The record is long and exact. Your copy is short and readable. Your job is selection and compression, not addition.

THE EVENT
The development comes with an event label. It names what this story is about.
- The headline must state that event.
- The title may reflect one article's angle. When the title and the event label point to different things, follow the event label.
- Use the event label only to decide the subject. Take every fact and figure from the summary.

SOURCE DISCIPLINE
- Every fact must come from the development. Add no outside knowledge and no interpretation of your own.
- Keep the certainty of the record. A plan stays a plan, and an offer that has not closed is not a completed deal.
- When you include an opinion or forecast, say who holds it.
- If the record gives two differing values for a fact, leave that fact out of the headline.

WHAT TO SELECT
Choose what an investor would act on or remember:
- The action and who took it.
- The size: amount, price, stake, or change.
- What it changes: control, ownership, capital structure, or outlook.
- Dates that are still ahead.
For a story with several stages, give the latest state and say briefly how it got there.
Leave out legal mechanics, intermediate entities, long descriptions of the company, and background the reader does not need.

NAMES AND TERMS
{names_and_terms}

NUMBERS AND DATES
{number_rules}
- Write dates as day and month, for example "9 November". Add the year only when it differs from the year of the AS OF date.
- Never use relative words such as "today", "yesterday", or a bare weekday.

HEADLINE
- One line, at most about 90 characters.
- Sentence case, present tense, active verb.
- State the event and its key figure. No question, no teaser, no colon.
- No dramatic or promotional words such as "jumbo", "soars", or "massive".

BLURB BY SLOT
lead: One paragraph of up to 4 sentences and at most about 80 words. Start with the event in more detail than the headline, then the main terms, then the basis or context, then what happens next and when.
story: 2 or 3 sentences and at most about 50 words. Give what the headline could not fit: the terms, the counterparty, the effect, and the next date.
flash: Return null.

For every slot:
- The blurb must not repeat the headline.
- Use plain declarative sentences. Never use a semicolon.
- If the development has too little to say beyond the headline, return null for the blurb.
- Write in English."""


def get_display_system_prompt(exchange: str):
    market_style = DISPLAY_MARKET_STYLE[exchange]
    return DISPLAY_SYSTEM_PROMPT_TEMPLATE.format(
        audience=market_style["audience"],
        cadence=market_style["cadence"],
        names_and_terms=market_style["names_and_terms"],
        number_rules=market_style["number_rules"],
    )


DISPLAY_USER_PROMPT = """Write the homepage copy for the development below.

AS OF: {as_of}

SLOT: {slot}

The development has an event label, a title, a summary, and its tickers.

DEVELOPMENT:
{development}

Return the response in the following JSON schema:
{format_instructions}"""