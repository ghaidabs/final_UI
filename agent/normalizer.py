import re

_DIGIT_RE = re.compile(r"\d")

def normalize_invoice_number(raw: str | None, company_slug: str) -> str | None:
    if not raw or not company_slug:
        return None

    text = raw.upper()
    slug = company_slug.upper()
    idx = text.find(slug)

    tail = text[idx + len(slug):] if idx != -1 else text
    digits = "".join(_DIGIT_RE.findall(tail))

    if len(digits) < 9:
        return None  # no guessing for missing digits, surface for clarification instead

    yyyymm, seq = digits[:6], digits[6:9]
    return f"{slug}_F{yyyymm}-{seq}"