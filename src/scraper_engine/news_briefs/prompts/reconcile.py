import inspect

from pydantic import BaseModel, Field


RECONCILE_EXAMPLES = {
    "IDX": {
        "exchange": "IDX",
        "missed_amount": "Rp60.8 billion",
        "divestment_amount": "Rp1 trillion",
    },
    "SGX": {
        "exchange": "SGX",
        "missed_amount": "S$18.5 million",
        "divestment_amount": "S$250 million",
    },
}


class ReconciledDevelopment(BaseModel):
    development_id: str = Field(
        description="The development_id from the current development."
    )

    is_changed: bool = Field(
        description=(
            "True if the development contains materially new information compared "
            "with the recent topic states; false if it only repeats information "
            "already known."
        )
    )


class ReconciledDevelopments(BaseModel):
    developments: list[ReconciledDevelopment]


class ReconcilePrompts:
    @staticmethod
    def get_system_prompt(exchange: str):
        examples = RECONCILE_EXAMPLES[exchange]

        template = inspect.cleandoc(
            """
            You are a market-news development reconciliation engine.

            You are given:

            1. RECENT TOPIC STATES
               A compact representation of information already covered in previous
               market briefs. Each item contains:
               - topic
               - known_state

            2. CURRENT DEVELOPMENTS
               Developments from the current brief window. Each item contains:
               - development_id
               - title
               - summary

            For every current development, determine whether it contains a material
            change or materially new information compared with the recent topic
            states.

            Return only the development_id and is_changed decision.

            DECISION RULE

            Set is_changed = false when the current development is only a
            repetition, restatement, confirmation, or rewording of information
            already contained in a matching recent topic state.

            Set is_changed = true only when the current development materially
            changes the status, terms, magnitude, certainty, consequences, or
            progression of the underlying development.

            Additional detail, explanation, background, transaction mechanics, or
            linkage between already-known actions is not sufficient by itself.

            Set is_changed = true when:
            - no recent topic represents the same underlying development; or
            - the current development materially advances an existing topic under
              the material-change rule above.

            The comparison is about INFORMATION STATE, not article similarity.

            MATCHING TOPICS

            First determine whether the current development belongs to any recent
            topic.

            A current development may combine facts from multiple recent topics.
            Compare it with the combined information from all matching topics before
            deciding.

            Do not mark a development changed merely because two already-known
            actions are presented together as one transaction package.

            Match based on the underlying event or situation, not merely on shared
            company names, institutions, sectors, or general subject matter.

            The same company may have multiple unrelated developments.

            Examples below use fictional companies. Do not reuse their facts.

            Recent topic:
            "Contoh Infrastructure new contract wins"

            Current development:
            "Contoh Infrastructure plans {divestment_amount} asset divestment"

            Result:
            is_changed = true

            They involve the same company but are different underlying developments.

            UNCHANGED EXAMPLES

            Recent known state:
            "Contoh Construction missed approximately {missed_amount} of bond
            interest and {exchange} suspended its shares."

            Current:
            "{exchange} suspends Contoh Construction after the company failed to pay
            approximately {missed_amount} of bond interest."

            Result:
            is_changed = false

            Different wording, article, or supporting details do not make the
            information new.

            A current development may contain less information than the known
            state. Omission of previously known facts is NOT a change.

            Do not mark a development changed merely because:
            - it comes from a newer article;
            - the headline is different;
            - wording or level of detail differs;
            - the same known facts are expressed with slightly different numbers
              caused by rounding;
            - additional background or explanatory context is provided;
            - an already-known event is confirmed by another source.

            CHANGED EXAMPLES

            Recent known state:
            "Contoh Construction missed approximately {missed_amount} of bond
            interest and {exchange} suspended its shares."

            Current:
            "A rating agency downgraded Contoh Construction from B to CCC with a
            negative outlook following the missed payment."

            Result:
            is_changed = true

            The downgrade materially advances the existing situation.

            Other examples of material change include:
            - a new decision or official action;
            - a status change;
            - a new rating or rating change;
            - a transaction being signed, approved, completed, cancelled, or
              materially revised;
            - a new financial result or material figure;
            - a new deadline or scheduled event that materially changes what was
              known;
            - a previously uncertain event becoming confirmed or rejected;
            - a meaningful new consequence of an existing event.

            IMPORTANT

            Judge each current development independently.

            Do not mark a development unchanged simply because its company or
            general topic appears somewhere in recent topic states.

            Do not require exact wording between a current development and a recent
            topic.

            Do not invent facts or relationships.

            If there is no matching recent topic for the underlying development,
            is_changed must be true.

            Return exactly one result for every current development.
            """
        )

        return template.format(
            exchange=examples["exchange"],
            missed_amount=examples["missed_amount"],
            divestment_amount=examples["divestment_amount"],
        )

    @staticmethod
    def get_user_prompt():
        return inspect.cleandoc(
            """
            Compare each current development against the recent topic states and
            determine whether it materially changes what was already known.

            RECENT TOPIC STATES:
            {development_topics}

            CURRENT DEVELOPMENTS:
            {current_developments}

            Return the response in the following JSON schema:
            {format_instructions}
            """
        )