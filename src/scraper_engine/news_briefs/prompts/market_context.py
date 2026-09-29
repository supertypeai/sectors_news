from dataclasses import dataclass


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