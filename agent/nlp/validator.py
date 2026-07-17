import re

_SPOKEN_DOT = re.compile(r"\s*\b(dot|point)\b\s*", re.IGNORECASE)
_SPOKEN_AT = re.compile(r"\s*\b(at|arobase)\b\s*", re.IGNORECASE)
_DIGIT_RUN_SPACING = re.compile(r"\b\d+(?:[\s-]+\d+){1,}\b")

_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+(?:\.[\w-]+)+\b")
_MATRICULE_FISCALE_RE = re.compile(r"\b\d{7}[A-Za-z]/[A-Za-z]/[A-Za-z]/\d{3}\b")
_IBAN_RE = re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b")
_LONG_DIGIT_RUN_RE = re.compile(r"\b\d{7,19}\b")

_INVOICE_CONTEXT_WORDS = {"facture", "invoice", "numero", "numéro", "number"}


def _normalize_spoken_symbols(text: str) -> str:
    text = _SPOKEN_DOT.sub(".", text)
    text = _SPOKEN_AT.sub("@", text)
    text = _DIGIT_RUN_SPACING.sub(lambda m: re.sub(r"[\s-]", "", m.group()), text)
    return text


def _shield_invoice_numbers(text: str, company_slug: str | None) -> tuple[str, dict[str, str]]:
    context_words = set(_INVOICE_CONTEXT_WORDS)
    if company_slug:
        context_words.add(company_slug.lower())

    pattern = re.compile(
        r"\b(?:" + "|".join(re.escape(w) for w in context_words) + r")\b"
        r"[^\d]{0,20}(\d{8,19})",
        re.IGNORECASE,
    )

    shielded: dict[str, str] = {}

    def repl(m: re.Match) -> str:
        token = f"§SHIELD{len(shielded)}§"
        shielded[token] = m.group(1)
        return m.group().replace(m.group(1), token)

    return pattern.sub(repl, text), shielded


def _unshield(text: str, shielded: dict[str, str]) -> str:
    for token, original in shielded.items():
        text = text.replace(token, original)
    return text


def redact_pii(text: str, company_slug: str | None = None) -> str:
    if not text or not text.strip():
        return text

    working = _normalize_spoken_symbols(text)
    working, shielded = _shield_invoice_numbers(working, company_slug)

    working = _EMAIL_RE.sub("<EMAIL>", working)
    working = _MATRICULE_FISCALE_RE.sub("<TAX_ID>", working)
    working = _IBAN_RE.sub("<IBAN>", working)
    working = _LONG_DIGIT_RUN_RE.sub("<PHONE>", working)

    return _unshield(working, shielded)