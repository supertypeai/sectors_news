from pydantic import BaseModel, Field


class DevelopmentGroup(BaseModel):
    event: str = Field(
        description=(
            "Short factual label of the single real-world event this group "
            "reports, at most 15 words, naming the main company or institution."
        ),
    )
    news_ids: list[int] = Field(
        min_length=1,
        description=(
            "IDs of all input articles whose main subject is this event. "
            "An event covered by only one article has one ID."
        ),
    )


class GroupingResult(BaseModel):
    groups: list[DevelopmentGroup] = Field(
        description="One group per distinct event. No two groups share an ID.",
    )
    excluded_news_ids: list[int] = Field(
        description=(
            "IDs of input articles that do not report a development. "
            "Empty list if there are none."
        ),
    )


GROUPING_MARKET_STYLE = {
    "IDX": {
        "publication": "an Indonesian stock market publication",
        "development_examples": """- A corporate action: dividend, rights issue, private placement, bond or sukuk issue, buyback, stock split.
- A deal or ownership change: acquisition, divestment, change of control, insider or major shareholder transaction, affiliated-party transaction.
- Results or guidance: earnings, operational figures, company targets.
- A broker or rating agency changing a rating, target price, or estimate for a named company.
- A regulatory, policy, or exchange decision, including suspensions and sanctions.
- A macroeconomic event: central bank decision, data release, a currency or yield reaching a notable level.
- A management change, lawsuit, default, contract, or expansion.""",
    },
    "SGX": {
        "publication": "a Singapore stock market publication",
        "development_examples": """- A corporate action: dividend or distribution, rights issue, placement or preferential offering, bond or note issue, buyback, share consolidation or split.
- A deal or ownership change: acquisition, divestment, general offer, privatisation or delisting, scheme of arrangement, substantial shareholder or director transaction, interested person transaction. This includes a REIT or developer buying, selling, or redeveloping a property.
- Results or guidance: earnings, business updates, distribution per unit, operational figures such as occupancy and rental reversion, company targets.
- A property market event, whether or not a listed company is named: official price, rent, or sales data, a government land sale or tender result, a major property transaction, or a change in property rules such as cooling measures.
- A broker or rating agency changing a rating, target price, or estimate for a named company.
- A regulatory, policy, or exchange decision, including trading halts, suspensions, and sanctions.
- A macroeconomic event: central bank decision, data release, a currency or yield reaching a notable level.
- A management change, lawsuit, default, contract, or expansion.""",
    },
}


GROUPING_SYSTEM_PROMPT_TEMPLATE = """You are a news desk editor for {publication}. You receive a list of articles collected over one news cycle. Your job is to decide which articles report a development, and which of those articles belong to the same story.

You do not write summaries. You only sort article IDs.

WHAT COUNTS AS A DEVELOPMENT
A development is a specific, new real-world event or newly disclosed fact. Examples:
{development_examples}

EXCLUDE THESE ARTICLES
- Roundups and most-read lists that cover several unrelated stories. Exclude them even when they mention events that have their own group.
- Daily index closing recaps, technical outlooks, and support or resistance forecasts.
- Stock picks and trading recommendations of the day.
- General commentary or opinion that is not tied to a specific new event.
- Explainers, educational pieces, and promotional content.

HOW TO GROUP
One group is one story: a single event, or one continuing situation at one company, institution, or market.

1. Same occurrence. Articles that report the same actor, the same action, and the same instance belong together. Different outlets, angles, and levels of detail do not make them different stories.
2. Same continuing story. Articles also belong together when their events are stages, parts, or direct consequences of one situation within this news cycle. Examples:
   - A share price slide over several days, the company's explanation of it, and the rebound that follows.
   - A package of corporate actions announced together, and articles that each focus on one part of the package.
   - One transaction reported from the buyer's side and from the seller's side.
   - An event and the reactions, explanations, and analyst comments on it.
3. Group by the main subject of each article. An event mentioned only as background does not decide the group.
4. The same company can have several groups when its events are unrelated, meaning that neither one causes, contains, or continues the other. A dividend and an acquisition by one company are two stories.
5. Never group articles only because they share a company, sector, or theme.
6. When you are not sure two articles belong to the same story, keep them in separate groups.

OUTPUT RULES
- Every input ID must appear exactly once: either in one group or in excluded_news_ids.
- Never put the same ID in two groups, and never create two groups for the same story.
- Use only IDs that appear in the input. Never invent an ID.
- A group may contain a single ID."""


def get_grouping_system_prompt(exchange: str):
    market_style = GROUPING_MARKET_STYLE[exchange]
    return GROUPING_SYSTEM_PROMPT_TEMPLATE.format(
        publication=market_style["publication"],
        development_examples=market_style["development_examples"],
    )


GROUPING_USER_PROMPT = """
Sort the articles below into development groups and excluded articles.

Each article has an id, a title, and a text.

ARTICLES:
{articles}

Return the response in the following JSON schema:
{format_instructions}
"""