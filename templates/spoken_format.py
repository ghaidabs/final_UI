_CURRENCY_NAMES = {
    "TND": {"fr": "Dinars Tunisiens", "en": "Tunisian Dinars"},
    "EUR": {"fr": "Euros", "en": "Euros"},
    "USD": {"fr": "Dollars", "en": "US Dollars"},
}

_STATUS_PHRASES = {
    "paid": {
        "fr": "a été payée",
        "en": "has been paid",
    },
    "draft": {
        "fr": "est encore un brouillon et n'a pas été envoyée",
        "en": "is still a draft and hasn't been sent",
    },
    "validated": {
        "fr": "a été validée",
        "en": "has been validated",
    },
    "cancelled": {
        "fr": "a été annulée",
        "en": "was cancelled",
    },
    "canceled": {
        "fr": "a été annulée",
        "en": "was cancelled",
    },
    "void": {
        "fr": "a été annulée",
        "en": "was cancelled",
    },
}

_DIGIT_WORDS = {
    "fr": ["zéro", "un", "deux", "trois", "quatre", "cinq", "six", "sept", "huit", "neuf"],
    "en": ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"],
}

_PLUS_WORD = {"fr": "plus", "en": "plus"}


def _lang(language: str | None) -> str:
    return "en" if (language or "fr").lower().startswith("en") else "fr"


def status_phrase(status: str | None, language: str = "fr") -> str:
    entry = _STATUS_PHRASES.get((status or "").lower())
    if not entry:
        # Unknown status
        if language == "en":
            return f"is currently {status}"
        return f"est actuellement au statut {status}"
    return entry.get(language, entry["fr"])


def spoken_currency(code: str | None, language: str = "fr") -> str:
    if not code:
        return ""
    entry = _CURRENCY_NAMES.get(code.upper())
    if not entry:
        return code
    return entry.get(language, entry["fr"])


def spoken_amount(value: float | None, currency: str | None, language: str = "fr") -> str:
    value = value or 0.0
    if value == int(value):
        amount_str = f"{int(value):,}".replace(",", " ")
    else:
        amount_str = f"{value:,.2f}".replace(",", " ")
    currency_str = spoken_currency(currency, language)
    return f"{amount_str} {currency_str}".strip()


def spoken_digit_group(group: str, language: str = "fr") -> str:
    words = _DIGIT_WORDS[_lang(language)]
    return " ".join(words[int(ch)] for ch in group if ch.isdigit())


def spoken_phone_number(phone: str | None, language: str = "fr") -> str:
    # +216 98 000 003 -> plus deux un six, neuf huit, zéro zéro zéro, zéro zéro trois
  
    if not phone:
        return phone or ""

    lang = _lang(language)
    spoken_parts = []
    for part in phone.strip().split():
        if part.startswith("+"):
            spoken_parts.append(f"{_PLUS_WORD[lang]} {spoken_digit_group(part[1:], lang)}".strip())
        else:
            spoken_parts.append(spoken_digit_group(part, lang))

    return ", ".join(p for p in spoken_parts if p)


def spoken_invoice_suffix(invoice_number: str | None, language: str = "fr") -> str:
    # ACME_F202605-001 -> deux zéro deux six zéro cinq, zéro zéro un
 
    if not invoice_number:
        return invoice_number or ""

    lang = _lang(language)
    suffix = invoice_number.split("_F", 1)[-1] if "_F" in invoice_number else invoice_number
    yyyymm, _, seq = suffix.partition("-")

    groups = [spoken_digit_group(yyyymm, lang)]
    if seq:
        groups.append(spoken_digit_group(seq, lang))

    return ", ".join(g for g in groups if g)


def display_amount(value: float | None, currency: str | None) -> str:
    value = value or 0.0
    amount_str = f"{int(value):,}" if value == int(value) else f"{value:,.2f}"
    amount_str = amount_str.replace(",", " ")
    
    return f"{amount_str} {(currency or '').upper()}".strip()