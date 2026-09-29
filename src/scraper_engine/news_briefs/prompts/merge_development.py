from pydantic import BaseModel, Field, model_validator

from .market_context import MARKET_CONTEXTS

import inspect


class DevelopmentMergeGroup(BaseModel):
    development_ids: list[str] = Field(
        min_length=1,
        description=(
            "IDs of input development objects that describe the same underlying "
            "real-world event."
        ),
    )

    merged_title: str | None = Field(
        default=None,
        description=(
            "Consolidated factual title. Required when more than one input "
            "development is grouped together. Null for a single development."
        ),
    )

    merged_summary: str | None = Field(
        default=None,
        description=(
            "Consolidated factual summary keeping every figure, currency, date, and "
            "hedge exactly as supplied. Required when more than one input "
            "development is grouped together. Null for a single development."
        ),
    )

    @model_validator(mode="after")
    def check_merged_fields(self):
        is_merged_group = len(self.development_ids) > 1
        is_missing_text = self.merged_title is None or self.merged_summary is None
        if is_merged_group and is_missing_text:
            raise ValueError(
                "merged_title and merged_summary are required when a group "
                "contains more than one development ID."
            )
        return self


class DevelopmentMergeResult(BaseModel):
    groups: list[DevelopmentMergeGroup] = Field(
        description=(
            "A partition of all supplied development IDs. Every input development "
            "ID must appear exactly once."
        ),
    )


def find_partition_errors(result: DevelopmentMergeResult, input_ids: set[str]):
    seen_ids: set[str] = set()
    duplicated_ids: set[str] = set()

    for group in result.groups:
        for development_id in group.development_ids:
            if development_id in seen_ids:
                duplicated_ids.add(development_id)
            seen_ids.add(development_id)

    return {
        "missing": input_ids - seen_ids,
        "duplicated": duplicated_ids,
        "unknown": seen_ids - input_ids,
    }


class MergeDevelopmentPrompts:
    @staticmethod
    def get_system_merge_development_prompt(exchange: str):
        context = MARKET_CONTEXTS[exchange]

        template = inspect.cleandoc(
            """
            You are a development-grouping system for a {market} equity-market
            intelligence product.

            You receive factual development objects that were independently
            extracted from different batches of news articles.

            Because the batches were processed independently, developments
            describing the same underlying real-world event may appear more than
            once.

            Your primary task is to partition the supplied development IDs into
            groups representing distinct underlying real-world events.

            You are NOT:
            - evaluating market importance or materiality;
            - selecting or ranking items for any brief;
            - excluding developments because they appear minor;
            - reprocessing the original news articles;
            - rewriting developments that do not need to be merged.

            DEVELOPMENT IDS

            Every supplied development has a unique Development ID.

            Every supplied Development ID must appear exactly once in the output.

            A Development ID must never:
            - be omitted;
            - appear in more than one group;
            - be changed;
            - be invented.

            GROUPING PRINCIPLE

            Put two or more development IDs in the same group only when they
            describe the same underlying real-world event, transaction, disclosure,
            decision, result, operational event, regulatory action, governance
            event, or continuing event.

            ILLUSTRATIONS BELOW USE FICTIONAL COMPANIES. Do not reuse their facts.

            Development A:
            "Contoh Telecom agrees to acquire Sample Digital"

            Development B:
            "Contoh Telecom discloses the transaction value of its Sample Digital
            acquisition"

            These may belong in the same group because they describe the same
            acquisition event.

            Do NOT group developments merely because:
            - they involve the same company;
            - they contain the same ticker;
            - they belong to the same sector;
            - they concern a similar theme;
            - they were reported close together;
            - one event may affect another;
            - they appeared in the same article.

            For example:

            "Telecom agrees to acquire Sample Digital"

            and

            "Telecom reports H1 2026 earnings"

            must remain separate groups.

            Be conservative. If it is unclear whether two developments describe the
            same underlying event, keep them in separate groups.

            EVENT STAGES

            Different disclosures may belong to the same continuing event when they
            represent additional facts, clarification, or progress within that same
            underlying event.

            For example:
            - an acquisition is announced;
            - its transaction value is later disclosed;
            - its expected completion date is later disclosed;

            may belong to the same acquisition event.

            However, a genuinely new or independent event must remain separate even
            when it involves the same company.

            SINGLETON GROUPS

            When a development does not have another development describing the
            same underlying event, return it as a group containing exactly one
            Development ID.

            For a singleton group:
            - do not rewrite the title;
            - do not rewrite the summary;
            - set merged_title to null;
            - set merged_summary to null.

            MULTI-DEVELOPMENT GROUPS

            When two or more developments describe the same underlying event, place
            their Development IDs together in one group.

            Only for these multi-development groups:
            - write one concise factual merged_title;
            - write one concise factual merged_summary;
            - consolidate complementary information from the grouped developments;
            - remove repetition;
            - preserve meaningful factual details.

            The merged title and summary must describe only the event represented
            by the grouped developments.

            Keep every figure, unit, date, and approximation marker exactly as
            supplied. Never round. Keep hedges such as "planned", "expected",
            "proposed", "about", and "reportedly" as supplied.

            {market_rules}

            Do not introduce:
            - facts absent from the supplied developments;
            - new companies;
            - new dates;
            - new amounts;
            - new percentages;
            - new causes;
            - new consequences;
            - market reactions;
            - predictions;
            - analyst opinions;
            - recommendations.

            If grouped developments contain conflicting factual claims, preserve
            the conflict or uncertainty neutrally rather than silently choosing one
            version.

            TICKERS AND SUPPORTING NEWS IDS

            Do not return tickers or supporting news IDs. The application preserves
            and combines them deterministically after grouping.

            Your responsibility is only:
            1. determine which Development IDs describe the same underlying event;
            2. provide a merged title and summary only when multiple developments
               are actually grouped.

            NO INFORMATION LOSS

            The output groups must form a complete partition of the supplied
            Development IDs:
            - every input Development ID appears;
            - every input Development ID appears exactly once;
            - no unknown Development ID appears.

            The output must follow the provided structured response schema exactly.
            """
        )

        return template.format(
            market=context.market,
            market_rules=context.market_rules,
        )

    @staticmethod
    def get_user_merge_development_prompt():
        return inspect.cleandoc(
            """
            Group the following development objects by underlying real-world event.

            Every development has a unique Development ID.

            Requirements:
            - every supplied Development ID must appear exactly once;
            - group IDs only when they describe the same underlying event;
            - keep independent developments separate;
            - for singleton groups, return null for merged_title and
              merged_summary;
            - for groups containing multiple developments, write one consolidated
              factual title and summary using only supplied information;
            - do not judge importance or materiality.

            DEVELOPMENTS:
            {developments}

            Return the response in the following JSON schema:
            {format_instructions}
            """
        )