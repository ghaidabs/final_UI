from agent.session import SessionState
import json
from pathlib import Path
from groq import Groq
from agent.validator import redact_pii 
from schemas.intents import (
    IntentType,
    CreateInvoiceIntent,
    LookupClientIntent,
    CheckInvoiceIntent,
    AddLineItemIntent,
    CheckPaymentIntent,
    ConfirmIntent,
    CancelIntent,
    UnknownIntent,
    LineItemInput,
)
import re
import logging
from agent.normalizer import normalize_invoice_number
from dotenv import load_dotenv

load_dotenv()

#logging.basicConfig(level=logging.INFO)
#logger = logging.getLogger(__name__)

PROMPT_PATH = Path(__file__).parent / "prompts" / "intent_extraction.txt"
SYSTEM_PROMPT = PROMPT_PATH.read_text()

client = Groq()  

_INTENT_MODEL_MAP = {
    IntentType.CREATE_INVOICE: CreateInvoiceIntent,
    IntentType.LOOKUP_CLIENT: LookupClientIntent,
    IntentType.CHECK_INVOICE: CheckInvoiceIntent,
    IntentType.ADD_LINE_ITEM: AddLineItemIntent,
    IntentType.CHECK_PAYMENT: CheckPaymentIntent,
    IntentType.CONFIRM: ConfirmIntent,
    IntentType.CANCEL: CancelIntent,
    IntentType.UNKNOWN: UnknownIntent,
}

_NUMBER_WORD_RE = re.compile(r"[-+]?\d+(?:[.,]\d+)?")


def _extract_price_via_llm(transcript: str) -> float | None:
    prompt = (
        "Extract only a numeric price from this short spoken answer. "
        "Respond ONLY with JSON: {\"price\": number or null}. "
        "If no clear price is stated, return null. Do not guess."
    )
    response = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": transcript},
        ],
        response_format={"type": "json_object"},
        temperature=0.0,
    )
    try:
        data = json.loads(response.choices[0].message.content)
        price = data.get("price")
        return float(price) if price is not None else None
    except (json.JSONDecodeError, TypeError, ValueError):
        return None


def extract_price_only(transcript: str) -> float | None:
    match = _NUMBER_WORD_RE.search(transcript.replace(",", "."))
    if match:
        try:
            return float(match.group().replace(",", "."))
        except ValueError:
            pass
    return _extract_price_via_llm(transcript)


def extract_intent(transcript: str, company_slug: str | None = None, language: str = "fr"):
    safe_transcript = redact_pii(transcript, company_slug)
    #if safe_transcript != transcript:
        #logger.info("PII redacted: %r -> %r", transcript, safe_transcript)

    response = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": safe_transcript},
        ],
        response_format={"type": "json_object"},
        temperature=0.1,
    )

    raw_text = response.choices[0].message.content

    try:
        raw = json.loads(raw_text) # Json string to dictionnary
    except json.JSONDecodeError:
        return UnknownIntent(
            intent=IntentType.UNKNOWN,
            raw_text=transcript,
            confidence=0.0,
            raw_transcript=transcript,
        )

    intent_type_str = raw.get("intent")
    try:
        intent_type = IntentType(intent_type_str) # converts to enum
    except ValueError:
        return UnknownIntent(
            intent=IntentType.UNKNOWN,
            raw_text=transcript,
            confidence=0.0,
            raw_transcript=transcript,
        )

    model_class = _INTENT_MODEL_MAP[intent_type]
    raw["raw_transcript"] = transcript
    raw["language"] = language
    raw.setdefault("confidence", 0.0) 
    raw.setdefault("low_confidence_fields", [])

    if intent_type in (IntentType.CHECK_INVOICE, IntentType.CHECK_PAYMENT, IntentType.ADD_LINE_ITEM):
        if intent_type == IntentType.ADD_LINE_ITEM:           
            candidate_number = raw.get("invoice_number") or ""
        else:
            candidate_number = raw.get("invoice_number") or transcript
        normalized = normalize_invoice_number(candidate_number, company_slug) if company_slug else raw.get("invoice_number")
        if normalized is None:
            raw["invoice_number"] = None
            raw["confidence"] = min(raw["confidence"], 0.4)
            if "invoice_number" not in raw["low_confidence_fields"]:
                raw["low_confidence_fields"].append("invoice_number")
        else:
            raw["invoice_number"] = normalized
            raw["confidence"] = max(raw["confidence"], 0.9)

    try:
        if "articles" in raw and raw["articles"] is not None:
            raw["articles"] = [LineItemInput(**item) for item in raw["articles"]]
        return model_class(**raw)
    except Exception:
        return UnknownIntent(
            intent=IntentType.UNKNOWN,
            raw_text=transcript,
            confidence=0.0,
            raw_transcript=transcript,
        )

def extract_intent_with_context(transcript: str, session: SessionState, language: str = "fr"):
    company_slug = session.user.company_slug
    if session.awaiting_field and session.pending_transcript:
        combined = (
            f"{session.pending_transcript}. "
            f"The user is now answering the question \"What is the {session.awaiting_field}?\" "
            f"with: \"{transcript}\". Use this value directly as the {session.awaiting_field} — "
        )
        return extract_intent(combined, company_slug=company_slug, language=language)
    return extract_intent(transcript, company_slug=company_slug, language=language)