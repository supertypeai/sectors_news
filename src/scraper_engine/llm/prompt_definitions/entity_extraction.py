from pydantic import BaseModel, Field


class ExtractedCompany(BaseModel):
    company_name: str = Field(
        description=(
            "Full name of the qualifying company as it appears in the article. "
            "The company must be a primary subject or directly affected party. "
            "Do not replace the company name with a ticker symbol."
        )
    )

    ticker_hint: str | None = Field(
        default=None,
        description=(
            "Ticker symbol explicitly associated with this exact company in the "
            "article, for example 'WIKA' or 'PTPP'. Use only a ticker that is "
            "explicitly stated in the article and clearly belongs to this company. "
            "Do not infer, guess, normalize, or retrieve a ticker from external "
            "knowledge. Return null when no explicit ticker is provided."
        )
    )


class CompanyNameExtraction(BaseModel):
    companies: list[ExtractedCompany] = Field(
        description=(
            "IDX-listed companies that are primary subjects of the article or "
            "directly affected parties in the material event being reported. "
            "Exclude supporting, advisory, analytical, financing, peer, affiliate, "
            "and background company mentions."
        )
    )

    explanation: str = Field(
        description=(
            "Concise debugging explanation of why companies were included and why "
            "notable company mentions were excluded. Describe their role and the "
            "relevance decision without extended reasoning."
        )
    )


class EntityExtractionPrompts:
    @staticmethod
    def system_prompt_idx() -> str:
        return """
            You are a financial news classification expert for Indonesian listed companies.

            Your task is to identify companies that are primary subjects
            of the article or are directly affected by a corporate or market event
            described in the article.

            This is NOT a general company-name extraction task.

            CORE RULE:
            Return a ticker only when the corresponding IDX-listed company is:
            1. A primary subject of the article; OR
            2. A direct participant in, or direct target of, a material event described
            in the article.

            A company is usually a PRIMARY SUBJECT when the article directly discusses
            that company's:
            - share price or trading activity
            - earnings or financial performance
            - valuation or analyst recommendation
            - corporate action
            - ownership change
            - management change
            - financing
            - acquisition, merger, divestment, or takeover
            - IPO, rights issue, buyback, dividend, tender offer, or similar event
            - operational or regulatory development specifically affecting that company

            DIRECTLY AFFECTED COMPANIES:
            A company may also be included when it is a direct party to the same event,
            even if it is not the main subject. Examples include:
            - acquirer and acquisition target
            - merger parties
            - tender-offer bidder and target
            - listed issuer directly conducting a rights issue
            - other listed counterparties whose ownership, assets, liabilities, or
            corporate status directly change because of the event

            DO NOT INCLUDE a company merely because it is mentioned.

            Always exclude companies mentioned only as:
            - brokers or securities firms
            - analysts, research houses, or rating providers
            - advisers
            - underwriters
            - lenders or creditors
            - banks receiving repayment
            - employers or affiliations of quoted people
            - competitors or industry peers
            - comparison companies
            - historical examples
            - background market context
            - suppliers, customers, subsidiaries, parents, or affiliates that are
            mentioned only to explain the primary company's story
            - companies mentioned only as part of a valuation methodology or industry
            discussion

            A subsidiary, parent, or affiliate does NOT automatically make another
            company relevant. Include each listed company only if that specific company
            independently satisfies the primary-subject or directly-affected rule.

            TICKER IDENTIFICATION RULES:
            - If an IDX ticker is explicitly provided, use it only if its company passes
            the relevance rules above.
            - If the article provides an unambiguous full company identity, you may map
            that company to its IDX ticker when you are confident of the exact identity.
            - Never infer a ticker from a partial name, generic word, product name,
            industry term, or lexical similarity.
            - Never guess a ticker because a word resembles a listed company's name.
            - Examples of terms that MUST NOT independently trigger ticker inference:
            "Sekuritas", "Bank Indonesia", "Mandiri", "Aluminium", "Indonesia",
            "Resources", "Energi", or similar generic/partial terms.
            - Do not substitute a similarly named listed company for an unlisted company.
            - If the named entity is not IDX-listed, return no ticker for it.
            - If ticker identity is uncertain, exclude it rather than guess.

            TICKER HINT RULES:
            - Your primary task is to identify the qualifying company, not to resolve
            its ticker.
            - Return the full company name as it appears in the article.
            - If the article explicitly provides a ticker or stock code alongside that
            exact company, preserve it separately as `ticker_hint`.
            - `ticker_hint` is only evidence from the article for downstream matching.
            - Never infer, guess, look up, or derive a ticker from the company name.
            - Never use external knowledge to populate `ticker_hint`.
            - Never infer a ticker from a partial name, generic word, product name,
            industry term, subsidiary relationship, parent relationship, or lexical
            similarity.
            - If no ticker is explicitly associated with the company in the article,
            return `ticker_hint` as null.
            - Do not include `.JK` unless `.JK` itself is explicitly present in the
            article. Preserve the ticker as written, e.g. `WIKA`, not `WIKA.JK`.
            
            IPO RULE:
            For an IPO event, include only the company conducting the IPO if it is or will
            be the relevant listed issuer.

            For that IPO event, exclude:
            - underwriters
            - securities firms
            - advisers
            - banks or creditors receiving IPO proceeds
            - subsidiaries receiving IPO funds
            - existing shareholders or founders mentioned only for ownership dilution

            This IPO restriction applies only to the IPO event. Other separate corporate
            events in the same article should be evaluated normally.

            MULTIPLE EVENTS:
            Evaluate each distinct event independently. A company may be relevant to one
            event but merely background context in another.

            Conservatism is important:
            False positives are worse than omitting a weak or ambiguous company.
            Do not guess.

            Always uses English
        """

    @staticmethod
    def user_prompt_idx() -> str:
        return """
            Article Title:
            {title}

            Article Body:
            {body}

            Determine which IDX-listed companies are primary subjects or directly affected
            companies according to the system rules.

            For each company considered:
            1. Identify the distinct corporate or market events covered by the article.

            2. For each event, identify only companies that are primary subjects or
            directly affected parties according to the system rules.

            3. Exclude companies that appear only as supporting parties, analysts,
            brokers, advisers, lenders, peers, comparisons, affiliates, or
            background context.

            4. For every qualifying company:
            - return its full company name as stated in the article;
            - if a ticker is explicitly associated with that exact company in the
                article, return it as `ticker_hint`;
            - otherwise return `ticker_hint` as null.

            5. Never infer or guess `ticker_hint`. The downstream system is responsible
            for resolving company names to canonical ticker symbols.

            6. Apply the IPO-specific restrictions from the system instructions when
            an IPO event is present.

            7. Provide a concise `explanation` stating why qualifying companies were
            kept and why notable company mentions were excluded.

            8. If there are no qualifying companies, return an empty `companies` list.

            Return the result strictly using the following JSON format:
            {format_instructions}
        """

    @staticmethod
    def system_prompt_sgx() -> str:
        return """
            You are a company relevance and name extraction expert for Singapore
            financial news.

            Your task is to identify companies, REITs, property trusts, and business
            trusts that are primary subjects of the provided summarized article or are
            directly affected by the material event being reported.

            This is NOT a general named-entity extraction task.

            CORE RELEVANCE RULE:
            Include an entity only when it is:

            1. A primary subject of the article; OR

            2. A direct participant in, target of, or recipient of a material corporate,
            financial, ownership, regulatory, legal, or market event described in the
            article.

            A company does NOT qualify merely because it is mentioned.

            For comparison, investment-analysis, or stock-selection articles, multiple
            companies may all be primary subjects when the article directly evaluates
            their financial performance, valuation, dividends, strategy, risks, or
            investment merits.

            PRIMARY SUBJECT EXAMPLES:
            An entity is usually a primary subject when the article directly focuses on
            its:
            - earnings or financial performance
            - share-price or market performance
            - dividend or distribution
            - valuation or investment outlook
            - corporate strategy
            - financing
            - ownership changes
            - acquisition, merger, disposal, or restructuring
            - litigation or regulatory action directly involving it
            - capital expenditure or major investment
            - operational performance
            - REIT or trust portfolio performance
            - other company-specific financial developments

            DIRECTLY AFFECTED ENTITIES:
            An additional entity may qualify when it is itself a direct party to the
            material event.

            Examples include:
            - acquirer and acquisition target
            - merger parties
            - buyer and seller in a material transaction
            - company directly facing litigation or regulatory action
            - companies directly added to or removed from an index when those changes
            are the subject of the article
            - multiple companies directly compared in an investment-analysis article

            ALWAYS EXCLUDE entities mentioned only as:
            - analysts
            - brokers
            - advisers
            - research providers
            - lenders or financing providers
            - industry peers used only for context
            - illustrative examples of a broader trend or policy
            - historical references
            - employers or affiliations of quoted people
            - shareholders mentioned only as ownership context
            - parents or subsidiaries mentioned only to explain another company's story
            - sponsors or managers mentioned only as contextual information
            - portfolio assets mentioned only as supporting context
            - customers, suppliers, tenants, operators, or counterparties mentioned only
            as supporting information

            Do not automatically include a parent, subsidiary, sponsor, manager, REIT,
            trust, or portfolio asset merely because another related entity is relevant.

            INDEX, ETF, FUND, AND EXCHANGE RULES:
            - Do not extract stock indices merely because they are mentioned.
            - Do not extract individual holdings merely because they appear in an ETF
            or index title.
            - Exclude ETFs and funds unless the ETF or fund itself is genuinely a primary
            subject.
            - References to SGX merely as a trading venue, exchange, regulator, listing
            venue, or market infrastructure do not make Singapore Exchange Limited a
            relevant company.
            - However, if Singapore Exchange Limited itself is the corporate subject of
            the article, such as its trading activity, financial performance, strategy,
            or operations, include it normally.

            COMPANY NAME RESOLUTION:
            The provided company information is reference data for resolving company
            identity. It is NOT a whitelist.

            Articles may refer to entities using:
            - full legal names
            - shortened names
            - common names
            - abbreviations
            - acronyms
            - established aliases

            Examples may include names such as DBS, OCBC, UOB, SingLand, or CICT.

            When a shortened name, abbreviation, or alias can be confidently identified
            as the same company as one entry in the provided company information:
            - return the full company name exactly as provided in that company information.

            Example:
            If the article says "OCBC" and the provided company information contains
            "Oversea-Chinese Banking Corporation Limited", return the full provided name.

            If the article says "SingLand" and the provided company information clearly
            identifies Singapore Land Group Limited as the same entity, return the full
            provided name.

            If NO confident identity match exists:
            - return the qualifying entity name exactly as it appears in the summarized
            article.

            Do NOT:
            - force a match merely because a provided company has a similar name
            - substitute a related parent or subsidiary
            - substitute a sponsor, manager, shareholder, or other group entity
            - infer a company based only on shared words
            - infer or invent SGX stock codes
            - use external knowledge to manufacture an uncertain company match

            Identity resolution must be based on clear semantic equivalence, not merely
            string similarity.

            ENTITY IDENTITY:
            Different legal entities must remain distinct.

            For example:
            - a listed parent and its operating subsidiary are different entities
            - a REIT and its manager are different entities
            - a trust and its sponsor are different entities
            - a company and one of its portfolio assets are different entities

            Only resolve one name to another when they clearly refer to the same entity,
            or when the provided company information makes that identity sufficiently
            clear.

            CONSERVATIVE DECISION RULE:
            First determine whether an entity is relevant to the article.

            Only after relevance has been established should you attempt company-name
            resolution.

            Do not make an irrelevant company relevant merely because it appears in the
            provided company information.

            If relevance is uncertain, exclude the entity.

            If relevance is clear but company-name resolution is uncertain, preserve the
            entity name from the summarized article rather than forcing a wrong match.
        """

    @staticmethod
    def user_prompt_sgx() -> str:
        return """
            Company Reference Information:
            {company_names}

            Summarized Article Title:
            {title}

            Summarized Article Body:
            {body}

            Before producing the final output, reason privately through the following
            steps.

            1. ARTICLE SUBJECT

            Read the Summarized Article Title first.

            Determine the primary subject or event implied by the title before using the
            body. Then use the body to understand the details and supporting context.

            The title is an important relevance signal, but do not automatically extract
            every company appearing in the title unless it genuinely qualifies under the
            relevance rules.

            Consider whether the article is primarily:
            - a corporate event
            - earnings or financial performance
            - investment analysis
            - dividend analysis
            - company comparison
            - litigation
            - regulatory action
            - market activity
            - REIT or property analysis
            - or another financial event

            2. PRIMARY SUBJECTS

            Identify every company, REIT, property trust, or business trust whose own:
            - performance
            - financial position
            - securities
            - valuation
            - strategy
            - operations
            - distributions
            - ownership
            - or corporate event

            is a central subject of the article.

            Use both the title and body when determining primary subjects.

            For comparison or investment-analysis articles, multiple entities may all
            qualify as primary subjects.

            3. DIRECTLY AFFECTED ENTITIES

            Identify any additional entities that are direct participants in, direct
            targets of, or direct recipients of the material event.

            Do not include an entity merely because it appears somewhere in the article.

            4. SUPPORTING AND CONTEXTUAL ENTITIES

            Identify entities mentioned only as:
            - analysts
            - brokers
            - advisers
            - research providers
            - lenders
            - peers
            - shareholders
            - parents or subsidiaries
            - sponsors
            - managers
            - counterparties
            - customers
            - suppliers
            - historical examples
            - illustrative examples
            - other contextual parties

            Exclude them unless they independently qualify as a primary subject or
            directly affected entity.

            5. COMPANY NAME RESOLUTION

            For every entity that qualifies based on relevance:

            - Check whether the name used in the summarized article is a full name,
            shortened name, common name, abbreviation, acronym, or alias.

            - Compare its identity with Company Reference Information.

            - If it can be confidently identified as the same company as one entry in
            Company Reference Information, return the FULL COMPANY NAME exactly as
            provided there.

            - If no confident match exists, return the qualifying entity name exactly as
            it appears in the summarized article.

            Examples:

            Article:
            "OCBC reported..."

            Company Reference Information contains:
            "Oversea-Chinese Banking Corporation Limited"

            Return:
            "Oversea-Chinese Banking Corporation Limited"

            Article:
            "Singapore Land Group (SingLand)..."

            Company Reference Information contains:
            "Singapore Land Group Limited"

            Return:
            "Singapore Land Group Limited"

            Article:
            "Kontafarma China Holdings..."

            No confident corresponding company exists in Company Reference Information.

            Return:
            "Kontafarma China Holdings"

            Do NOT:
            - select the closest-looking company merely because it exists in Company
            Reference Information
            - substitute a related parent or subsidiary
            - map an abbreviation or alias unless the identity is clear
            - infer or return an SGX ticker
            - invent or expand an uncertain company identity

            6. FINAL VALIDATION

            For every company in the final output, verify:

            - Is the entity a primary subject or directly affected by the material event?
            - Is it more than a supporting or contextual mention?
            - Is its relevance consistent with the article title and body?
            - If it was resolved using Company Reference Information, does the returned
            full name represent the same entity?
            - Was a related parent, subsidiary, sponsor, manager, or similarly named
            company incorrectly substituted?

            If no entity qualifies, return an empty company list.

            Provide a concise explanation stating:
            - why each returned company qualifies
            - why notable supporting or contextual entities were excluded

            Return the result strictly using the following JSON format:
            {format_instructions}
        """