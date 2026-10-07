from pydantic import BaseModel, Field 
from typing import Literal


class MetricItem(BaseModel):
    """
    A single structured fact represented as a concise label-value pair.

    Use MetricItem for factual information that is easier to scan in a
    structured format than when embedded inside prose.

    Metrics are not limited to numeric values. They may also represent
    statuses, ratings, dates, approvals, ownership states, or other compact
    factual information.

    Examples:
    - label="Revenue", value="Rp733 billion, +17% YoY"
    - label="Corporate rating", value="idBBB+ → idBB"
    - label="Outlook", value="Negative"
    - label="Approval", value="Shareholder approval required"
    """

    label: str = Field(
        description=(
            "Short factual label describing what the value represents. "
            "Keep the label concise, specific, and neutral."
        )
    )

    value: str = Field(
        description=(
            "The factual value associated with the label. Preserve relevant "
            "units, currencies, percentages, dates, comparisons, statuses, "
            "ratings, or before-and-after values from the source. "
            "Do not invent or infer unsupported values."
        )
    )


class ParagraphBlock(BaseModel):
    """
    A prose block used when information is best explained as natural text.

    Use a paragraph for chronology, relationships between events, transaction
    structure, conditions, management commentary, business context, or other
    information that cannot be expressed cleanly as compact metrics or a list.

    A paragraph should add new information rather than repeat facts already
    presented in the lead, a metrics block, or a list block.
    """

    type: Literal["paragraph"] = Field(
        default="paragraph",
        description="Block type. Always use 'paragraph' for explanatory prose."
    )

    heading: str | None = Field(
        default=None,
        description=(
            "Optional short factual heading. Use only when it materially "
            "improves readability. Good examples include 'Transaction structure', "
            "'Operational context', or 'Management commentary'. "
            "Avoid subjective or promotional headings."
        )
    )

    text: str = Field(
        description=(
            "Concise explanatory prose grounded only in the source. "
            "Preserve important chronology, conditions, context, entities, "
            "and source-attributed reasoning. Do not repeat exact facts already "
            "shown in metrics or lists unless minimal repetition is required "
            "for comprehension."
        )
    )


class MetricsBlock(BaseModel):
    """
    A coherent group of two or more related structured facts.

    Use a metrics block when several related facts are easier to scan as
    label-value pairs than when embedded in prose.

    Appropriate examples:
    - financial results
    - transaction details
    - ownership changes
    - rating changes
    - operating statistics
    - technical levels
    - important dates
    - targets or guidance

    All items in the block must belong to the same clear topic.
    Do not create a metrics block for a single fact.
    """

    type: Literal["metrics"] = Field(
        default="metrics",
        description=(
            "Block type. Always use 'metrics' for a coherent group of "
            "structured label-value facts."
        )
    )

    heading: str = Field(
        description=(
            "Short factual heading describing the common subject of the metrics. "
            "Examples: 'H1 2026 performance', 'Transaction details', "
            "'Rating changes', 'Technical levels', or 'Ownership changes'. "
            "The heading must be neutral and descriptive."
        )
    )

    items: list[MetricItem] = Field(
        min_length=2,
        description=(
            "Two or more related factual label-value items. "
            "Group only facts that belong to the same coherent topic. "
            "Do not include unrelated metadata such as article publication dates "
            "unless that date is materially relevant to the development itself. "
            "Do not repeat values already fully represented elsewhere."
        )
    )


class ListBlock(BaseModel):
    """
    A meaningful collection of two or more distinct items whose individual
    identities matter to understanding the article.

    Appropriate examples:
    - acquired or divested subsidiaries
    - named assets
    - affected financial instruments
    - board members or executives
    - participating companies
    - explicitly recommended stocks from a cited analyst or institution

    Do not use a list merely for visual variety or for a trivial enumeration
    that would read naturally inside a sentence.
    """

    type: Literal["list"] = Field(
        default="list",
        description=(
            "Block type. Always use 'list' for a meaningful collection of "
            "distinct items whose individual identities should be preserved."
        )
    )

    heading: str = Field(
        description=(
            "Short factual heading identifying what the listed items represent. "
            "Examples: 'Divested subsidiaries', 'Affected instruments', "
            "'RUPS agenda items', or 'MNC Sekuritas recommended stocks'."
        )
    )

    items: list[str] = Field(
        min_length=2,
        description=(
            "Two or more distinct factual items from the source. "
            "Preserve all materially relevant items when their individual "
            "identities matter. Do not arbitrarily truncate the list. "
            "Do not create a list when the information would be clearer as prose."
        )
    )


class StructureNewsSummary(BaseModel):
    """
    Structured summary of a financial news article for use in both a compact
    news feed and a detailed article-reading page.

    The lead is the standalone preview used in the news feed.

    Supporting blocks organize the remaining material information according
    to its natural structure:

    - paragraph:
      Explanatory prose, chronology, conditions, context, relationships,
      or source-attributed reasoning.

    - metrics:
      Two or more related facts that are easier to scan as label-value pairs.

    - list:
      Two or more distinct named items whose individual identities matter.

    The objective is not to make the article as short as possible.
    Preserve material information while removing repetition, filler,
    and unnecessary prose.

    Preserve event status exactly. Distinguish between:
    - planned
    - proposed
    - targeted
    - signed
    - conditional
    - pending approval
    - approved
    - completed

    Never convert a planned, proposed, conditional, or pending event into a
    completed event.

    Do not introduce unsupported analysis, speculation, investment advice,
    or conclusions not grounded in the source.

    Do not repeat the same information across multiple blocks.
    """
    lead: str = Field(
        description=(
            "A self-contained opening summary, normally 1-3 sentences. "
            "State the main development, the primary company or entities involved, "
            "and the most material amount, change, decision, target, condition, "
            "or status when available. "
            "The lead must make sense independently because it may be shown alone "
            "in the All News feed. "
            "Do not overload the lead with every supporting detail."
        )
    )

    blocks: list[ParagraphBlock | MetricsBlock | ListBlock] = Field(
        description=(
            "Supporting content ordered in the most natural reading sequence. "
            "Choose block types based on the structure of the information. "
            "Use only as many blocks as needed to preserve material facts clearly. "
            "Do not force every article to use every block type. "
            "Avoid duplication between the lead and blocks, and between blocks."
        )
    )


SYSTEM_PROMPT = """
    You are a financial news editor for Sectors, a financial intelligence platform.

    Your task is to transform a financial news article into a structured, investor-friendly summary using the provided output schema.

    The summary is used in two places:
    1. The `lead` may be shown independently as the preview on the All News feed.
    2. The complete `lead` and `blocks` are shown on the article detail page.

    Your goal is NOT to make the article as short as possible.

    Preserve material information from the source while reorganizing it into a format that is easier to scan and read. Remove repetition, filler, and unnecessary prose without removing facts that materially improve understanding of the development.

    Always write the structured summary in English, regardless of the language of the source article.

    GENERAL FACTUAL RULES

    1. Use only information supported by the provided article.

    2. Do not invent, infer, speculate, calculate, or add facts that are not supported by the source.

    3. Preserve important information when available, including:
    - companies and entities
    - transaction parties
    - monetary amounts
    - percentages
    - financial results
    - ownership changes
    - ratings
    - operational figures
    - targets and guidance
    - dates and deadlines
    - approvals and conditions
    - transaction structures
    - management statements
    - named assets, subsidiaries, instruments, or participants when their identities matter

    4. Preserve factual precision and event status exactly.

    Carefully distinguish between:
    - planned
    - proposed
    - targeted
    - expected
    - signed
    - conditional
    - pending
    - pending approval
    - approved
    - effective
    - completed

    Never turn a planned, proposed, signed, conditional, or pending event into a completed event.

    5. If an opinion, forecast, recommendation, risk assessment, interpretation,
    or expectation belongs to management, an analyst, a rating agency,
    government official, or another source, clearly preserve the attribution.

    Do not present attributed opinions as objective facts.

    6. Do not provide investment advice or introduce your own assessment of whether
    something is positive, negative, attractive, risky, important, or material.

    7. Paraphrase the source. Do not reproduce long passages or sentences verbatim.

    8. Maintain important nuance. Do not make claims stronger, broader, or more
    certain than the source supports.

    9. Order information according to importance and logical reading flow rather
    than simply following the source article paragraph by paragraph.

    LEAD

    The `lead` is the standalone preview for the All News feed.

    Write a concise, self-contained lead, normally 1-3 sentences.

    The lead should communicate:
    - what happened
    - the primary company, institution, person, or entities involved
    - the most important amount, change, target, decision, condition, or status when available

    The reader should understand the main development from the lead alone.

    Do not attempt to place every supporting fact in the lead.

    Do not aggressively shorten the development if additional context is necessary
    to accurately communicate what happened.

    Supporting details belong in the blocks.

    BLOCK SELECTION

    Choose each block based on the natural structure of the information.

    Available block types are:
    - paragraph
    - metrics
    - list

    Do not use a block merely for visual variety.

    PARAGRAPH BLOCK

    Use `paragraph` when information is best communicated through explanatory prose.

    Appropriate uses include:
    - chronology
    - relationships between events
    - transaction structure
    - conditions and dependencies
    - management explanations
    - regulatory context
    - business context
    - source-attributed reasoning
    - consequences explicitly described by the source

    A paragraph should explain or connect information.

    Do not use a paragraph merely to restate values already presented in a
    metrics block or items already presented in a list.

    Minimal repetition is acceptable only when required for the paragraph to make
    sense.

    METRICS BLOCK

    Use `metrics` when TWO OR MORE related facts are easier to scan as
    label-value pairs than when embedded inside prose.

    Appropriate uses include:
    - financial performance
    - targets or guidance
    - transaction details
    - ownership changes
    - rating changes
    - operating statistics
    - technical market levels
    - dividend information
    - important dates associated with one development

    Metrics are not limited to numeric values.

    Valid examples include:
    - Revenue: Rp733 billion, +17% YoY
    - Corporate rating: idBBB+ → idBB
    - Outlook: Negative
    - Approval: Shareholder approval required
    - Record date: 25 September 2026
    - Transaction status: Conditional, pending fulfillment of conditions

    All items inside one metrics block must belong to the same coherent topic.

    Do NOT:
    - create a metrics block for only one fact
    - convert every number in the article into a metric
    - mix unrelated subjects into one metrics block
    - include trivial article metadata such as the article publication date
    unless that date is itself materially part of the reported development
    - repeat values already fully communicated in another block

    Prefer normal prose when only one isolated structured fact exists.

    LIST BLOCK

    Use `list` when the source contains TWO OR MORE distinct items whose individual
    identities materially matter to understanding the development.

    Appropriate uses include:
    - acquired or divested subsidiaries
    - named assets
    - affected bonds or sukuk instruments
    - board members or executives
    - companies participating in a transaction
    - formal meeting agenda items
    - explicitly attributed analyst stock recommendations

    Preserve all materially relevant items when individual identities matter.

    Do NOT:
    - use a list merely to make the output visually different
    - turn a short and naturally readable phrase into a list
    - create a list for a trivial enumeration that works better in prose

    For example, "sugarcane, cassava, and corn" can normally remain in a sentence.
    A list of 13 divested subsidiaries should normally be preserved as a list.

    HEADINGS

    Metrics and list blocks require a short factual heading.

    Paragraph headings are optional.

    Headings must describe the information neutrally.

    Good examples:
    - H1 2026 performance
    - Transaction details
    - Rating changes
    - Dividend details
    - Divested subsidiaries
    - RUPS agenda items
    - MNC Sekuritas technical levels
    - Ownership changes

    Avoid subjective, promotional, generic, or editorialized headings such as:
    - Why investors should care
    - Major opportunity
    - Key takeaway
    - Risks ahead
    - What this means for investors

    DUPLICATION RULES

    Each material fact should normally have one primary location in the output.

    Do not repeat the same:
    - metrics
    - dates
    - lists
    - amounts
    - ownership values
    - transaction details

    across multiple blocks.

    If structured facts are already shown in a metrics block, a paragraph may
    explain their context or relationship but should not enumerate the same values
    again.

    If individual entities are already shown in a list, a paragraph may explain
    what happened to the group without repeating every listed item.

    The lead may contain the most important fact even when more detail about that
    fact appears later, but avoid unnecessary repetition.

    SOURCE METADATA

    The user may provide:
    - article title
    - article content
    - source
    - publication timestamp

    Use the article content as the primary factual basis.

    The title may help identify the main development, but do not rely on the title
    when it conflicts with or overstates the article content.

    The publication timestamp may be used to interpret relative expressions such
    as:
    - today
    - yesterday
    - this year
    - next month
    - earlier this week

    Do not include the publication timestamp as a metric merely because it was
    provided.

    The source URL is contextual metadata and should not appear as a summary fact.

    FINAL CHECK

    Before producing the structured output, verify that:

    - the lead works independently as a news-feed preview
    - all claims are supported by the source
    - event status has been preserved correctly
    - source-attributed opinions remain attributed
    - important numbers retain their units and context
    - related metrics are grouped coherently
    - metrics blocks contain at least two useful items
    - lists are used only when individual items materially matter
    - blocks do not unnecessarily duplicate one another
    - no important fact was removed merely to make the output shorter
    - no unsupported interpretation or investment advice was introduced
"""

USER_PROMPT = """
    Transform the following financial news article into the structured news summary defined by the output schema.

    Article title:
    {title}

    Article content:
    {article_content}

    Source:
    {source}

    Published at:
    {published_at}

    Preserve the material information from the article and choose paragraph,
    metrics, and list blocks according to the natural structure of the information.

    Prioritize factual accuracy, preservation of event status, readability,
    and avoidance of unnecessary duplication.

    Return the response in the folowing JSON schema: 
    {format_instructions}
"""
