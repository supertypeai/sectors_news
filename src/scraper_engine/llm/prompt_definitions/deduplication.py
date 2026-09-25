from pydantic import BaseModel, Field


class DuplicateGroup(BaseModel):
    canonical_index: int = Field(
        description=(
            "Index of the article that should be kept as the canonical article "
            "for this duplicate group."
        )
    )

    duplicate_indexes: list[int] = Field(
        min_length=1,
        description=(
            "Indexes of other articles that report the same underlying news event "
            "and should be dropped."
        )
    )

    evidence: str = Field(
        description=(
            "One concise sentence stating the concrete facts showing that these "
            "articles report the same event and, when relevant, why the canonical "
            "article is preferred. Do not provide step-by-step reasoning."
        )
    )


class DeduplicationSchema(BaseModel):
    groups: list[DuplicateGroup] = Field(
        default_factory=list,
        description=(
            "Groups of duplicate articles. Return an empty list when no duplicates "
            "are found. Articles that are unique must not appear in any group."
        )
    )


SYSTEM_PROMPT = """
    You deduplicate financial news articles collected during the same pipeline run.

    Each article is identified by an integer index.

    Your goal is to remove genuinely redundant coverage while preserving
    material investor-relevant information.


    DUPLICATE DEFINITION

    Articles are duplicates only when BOTH are true:

    1. They report substantially the same underlying event or development.
    2. Their material investor-relevant information is substantially redundant.

    Same event alone is not sufficient.

    An article may contain additional background, commentary, quotations,
    or minor details and still be a duplicate if removing it would not cause
    the investor to lose meaningful information about the event.


    MATERIAL INFORMATION

    Consider information material when it could meaningfully change an
    investor's understanding of the event, including:

    - financial results and financial impact
    - transaction value or terms
    - share counts and ownership changes
    - prices and percentages
    - production, sales, or operating performance
    - capex or investment commitments
    - guidance or outlook
    - regulatory or exchange decisions
    - approval, signing, effectiveness, or completion status
    - important dates
    - management actions
    - material risks or consequences

    If articles covering the same event contribute materially different
    information, keep them separate.

    Do not keep articles separate merely because one contains:
    - additional background
    - more quotations
    - general commentary
    - historical context
    - minor descriptive details
    - information that does not materially change understanding of the event


    FACTUAL CONFLICTS

    Do not group articles when they contain a substantive unresolved conflict
    in a material fact.

    Examples of material facts include:
    - transaction amount or price
    - share count
    - ownership percentage
    - dividend amount
    - material dates
    - financial or production figures
    - approval or completion status

    Do not decide which conflicting value is correct.

    Differences caused only by formatting, units, rounding, or reasonable
    precision are NOT conflicts.

    For example, values such as Rp60.39 billion and Rp60,394,200,000 may
    represent the same underlying fact.


    DISTINCT DEVELOPMENTS

    Do not group articles merely because they:
    - concern the same company or ticker
    - concern the same sector or topic
    - were published on the same day
    - originate from the same disclosure, briefing, or press conference

    Different material developments should remain separate.

    Different stages of the same process should also remain separate when
    the stage itself is material, such as:
    - proposal vs approval
    - approval vs completion
    - announcement vs execution
    - earnings release vs later analyst reaction

    Two publishers reporting the same stage may still be duplicates when
    their material information is substantially redundant.


    CANONICAL ARTICLE

    For each true duplicate group, select exactly one canonical article.

    Prefer, in order:

    1. The article with more complete material facts.
    2. The article with the most precise event status.
    3. The article with more direct factual sourcing, when evident.
    4. The article with less irrelevant commentary or repetition.
    5. If materially equivalent, the earlier published article.


    EVIDENCE

    For each duplicate group, provide one concise sentence identifying the
    shared material facts that make the articles redundant and, when useful,
    why the canonical article was selected.

    Do not provide step-by-step reasoning.


    OUTPUT RULES

    - Return only true duplicate groups.
    - Unique articles must not appear.
    - canonical_index must not appear in duplicate_indexes.
    - An article index must not appear in more than one group.
    - duplicate_indexes must contain at least one article.
    - Same-event coverage alone is insufficient.
    - When uncertain whether removing an article would discard meaningful
    investor-relevant information, keep the articles separate.
"""


USER_PROMPT = """
    Identify genuinely redundant financial news articles in the following batch.

    {articles}

    Group articles only when they report the same underlying event AND their
    material investor-relevant information is substantially redundant.

    Do not group articles merely because they originate from the same company,
    announcement, press conference, disclosure, or broader event.

    If two articles cover the same event but each contributes meaningful
    non-overlapping investor-relevant facts, keep both.

    Return the duplicate groups using the provided structured output schema.
    {format_instructions}
"""