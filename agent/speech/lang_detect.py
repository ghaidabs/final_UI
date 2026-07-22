from __future__ import annotations

SUPPORTED_LANGUAGES = ("fr", "en")
DEFAULT_LANGUAGE = "fr"


def detect_language(text: str | None) -> str:
    if not text or not text.strip():
        return DEFAULT_LANGUAGE
    try:
        from langdetect import detect
        code = detect(text).lower().split("-")[0]
    except Exception:
        return DEFAULT_LANGUAGE
    return code if code in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE


def resolve_language(tag: str | None, text: str | None = None) -> str:
    base = (tag or "").strip().lower().split("-")[0]
    if base in SUPPORTED_LANGUAGES:
        return base
    return detect_language(text)