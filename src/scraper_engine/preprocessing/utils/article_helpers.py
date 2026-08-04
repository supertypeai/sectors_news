import re


def is_raw_ticker(text: str) -> bool:
    cleaned = text.strip()
    return bool(re.match(r"^[A-Z]{2,6}$", cleaned))


def normalize_idx_company_name(raw: str) -> str:
    name = re.sub(r"^\s*PT\s+", "", raw, flags=re.IGNORECASE)
    name = re.sub(r"\s*Tbk\.?$", "", name, flags=re.IGNORECASE)
    name = re.sub(r"\s*\(Persero\)\s*", " ", name, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", name).strip().lower()


def normalize_sgx_company_name(raw: str) -> str:
    name = re.sub(r"\s*Ltd\.?$", "", raw, flags=re.IGNORECASE)
    name = re.sub(r"\s*Limited\.?$", "", name, flags=re.IGNORECASE)
    name = re.sub(r"\s*Pte\.?$", "", name, flags=re.IGNORECASE)
    name = re.sub(r"\s*Bhd\.?$", "", name, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", name).strip().lower()


def clean_article(article_text: str) -> str:
    pattern = re.compile(r"^Baca juga:.*$", re.IGNORECASE | re.MULTILINE)
    text_without_baca_juga = pattern.sub("", article_text)
    cleaned_text = re.sub(r"\n{3,}", "\n\n", text_without_baca_juga)
    return cleaned_text.strip()


def basic_cleaning_body(body: str) -> str:
    body = re.sub(r"\([^)]*ticker[^)]*\)", "", body, flags=re.IGNORECASE)
    body = re.sub(r"\s+", " ", body)
    return body.strip()


def clean_apostrophe_case(body: str) -> str:
    pattern = r"(’|')([A-Z])\b"

    def replacer(match):
        return match.group(1) + match.group(2).lower()

    return re.sub(pattern, replacer, body)


def normalize_company_abbreviations(body: str) -> str:
    cleaned_body = re.sub(r"\bPt\.?\b", "PT", body, flags=re.IGNORECASE)
    return re.sub(r"\bTbk\b", "Tbk", cleaned_body, flags=re.IGNORECASE)


def normalize_dot_case(body: str) -> str:
    pattern_thousands = r"(\d)\.(\d{3})(?!%)"

    while re.search(pattern_thousands, body):
        body = re.sub(pattern_thousands, r"\1,\2", body)

    pattern_decimals = r"(\d),(\d{1,2})(?![\d,])"
    return re.sub(pattern_decimals, r"\1.\2", body)
