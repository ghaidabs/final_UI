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
)
from schemas.responses import VoiceResponse
from agent.session import SessionState
from agent.normalizer import normalize_invoice_number
from agent.nlu import extract_price_only
from api.mock_saas_client import MockSaasClient
from templates.invoice import (
    build_invoice_draft_spoken,
    build_invoice_details_spoken,
    build_invoice_list_spoken,
    build_line_item_added_spoken,
)
from templates.client_lookup import build_client_spoken
from templates.payment_status import build_payment_status_spoken
from templates.clarification import t

CONFIDENCE_THRESHOLD = 0.7


async def dispatch(intent, saas: MockSaasClient, session: SessionState) -> VoiceResponse:
    language = getattr(intent, "language", "fr")

    RECOVERABLE = {"invoice_number", "unit_price"}

    if intent.confidence < CONFIDENCE_THRESHOLD:
        flagged = set(intent.low_confidence_fields)
        if flagged and flagged <= RECOVERABLE:
            if isinstance(intent, AddLineItemIntent):
                return await _add_line_item(intent, saas, session)
            if isinstance(intent, CreateInvoiceIntent):
                return await _create_invoice_draft(intent, saas, session)

        prompt = _clarification_prompt(intent)
        return VoiceResponse(
            success=False,
            spoken_text=prompt,
            clarification_question=prompt,
        )

    match intent:
        case ConfirmIntent():
            return await _handle_confirm(session, saas, language)
        case CancelIntent():
            return await _handle_cancel(session, saas, language)
        case LookupClientIntent():
            return await _lookup_client(intent, saas, session)
        case CheckPaymentIntent():
            return await _check_payment(intent, saas)
        case CheckInvoiceIntent():
            return await _check_invoice(intent, saas)
        case CreateInvoiceIntent():
            return await _create_invoice_draft(intent, saas, session)
        case AddLineItemIntent():
            return await _add_line_item(intent, saas, session)
        case UnknownIntent():
            return VoiceResponse(
                success=False,
                spoken_text=t("unknown_intent", language),
                error="unknown_intent",
            )
        case _:
            return VoiceResponse(
                success=False,
                spoken_text=t("unhandled_intent", language),
                error="unhandled_intent_type",
            )


async def _resolve_single_client(client_name: str, saas: MockSaasClient, language: str, session: SessionState, original_intent=None):
    matches = await saas.lookup_client(client_name)
    if len(matches) == 0:
        return VoiceResponse(
            success=False,
            spoken_text=t("client_not_found", language, client_name=client_name),
            error="client_not_found",
        )
    if len(matches) == 1 and "_fuzzy_score" not in matches[0]:
        return matches[0]

    names = ", ".join(f"{m['first_name']} {m['last_name']}" for m in matches)

    if len(matches) == 1 and original_intent is not None:
        session.pending_disambiguation = {
            "kind": "client",
            "candidate": matches[0],
            "resume_intent": original_intent.intent.value,
            "original_intent": original_intent,
        }
        question = t("client_confirm_single", language, names=names)
        return VoiceResponse(
            success=False,
            spoken_text=question,
            clarification_question=question,
            requires_confirmation=True,
            display_data=matches,
        )

    question = t("client_confirm_multiple", language, names=names)
    return VoiceResponse(
        success=False,
        spoken_text=question,
        clarification_question=question,
        display_data=matches,
    )


async def _lookup_client(intent: LookupClientIntent, saas: MockSaasClient, session: SessionState) -> VoiceResponse:
    result = await _resolve_single_client(
        intent.client_name, saas, intent.language, session, original_intent=intent
    )
    if isinstance(result, VoiceResponse):
        return result
    client = result
    return VoiceResponse(
        success=True,
        spoken_text=build_client_spoken(client, language=intent.language),
        display_data=client,
    )


def _has_target(intent) -> bool:
    invoice_number = getattr(intent, "invoice_number", None)
    client_name = getattr(intent, "client_name", None)
    return bool(invoice_number) or bool(client_name and client_name.strip())


async def _check_payment(intent: CheckPaymentIntent, saas: MockSaasClient) -> VoiceResponse:
    if not _has_target(intent):
        question = t("invoice_or_client_missing", intent.language)
        return VoiceResponse(
            success=False,
            spoken_text=question,
            clarification_question=question,
        )

    if intent.invoice_number:
        inv = await saas.get_invoice(intent.invoice_number)
        invoices = [inv] if inv else []
    else:
        invoices = await saas.get_invoices_by_client(intent.client_name)

    if not invoices:
        return VoiceResponse(
            success=False,
            spoken_text=t("invoice_not_found", intent.language),
            error="invoice_not_found",
        )

    return VoiceResponse(
        success=True,
        spoken_text=build_payment_status_spoken(invoices, language=intent.language),
        display_data=invoices,
    )


async def _check_invoice(intent: CheckInvoiceIntent, saas: MockSaasClient) -> VoiceResponse:
    if not _has_target(intent):
        question = t("invoice_or_client_missing", intent.language)
        return VoiceResponse(
            success=False,
            spoken_text=question,
            clarification_question=question,
        )

    if intent.invoice_number:
        inv = await saas.get_invoice(intent.invoice_number)
        invoices = [inv] if inv else []
    else:
        invoices = await saas.get_invoices_by_client(intent.client_name)

    if not invoices:
        return VoiceResponse(
            success=False,
            spoken_text=t("invoice_not_found", intent.language),
            error="invoice_not_found",
        )

    spoken = (
        build_invoice_details_spoken(invoices[0], language=intent.language)
        if len(invoices) == 1
        else build_invoice_list_spoken(invoices, language=intent.language)
    )

    return VoiceResponse(
        success=True,
        spoken_text=spoken,
        display_data=invoices,
    )


def _line_item_from_product(item, product: dict) -> dict:
    designation = product["designation"]
    return {
        "name": designation,
        "designation": designation,
        "description": "",
        "quantity": item.quantity,
        "unit_price": item.unit_price,
        "total_ht": round(item.quantity * item.unit_price, 3),
        "unit": item.unit or "piece",
    }


def _line_item_from_raw_name(item) -> dict:
    return {
        "name": item.product_name,
        "designation": item.product_name,
        "description": "",
        "quantity": item.quantity,
        "unit_price": item.unit_price,
        "total_ht": round(item.quantity * item.unit_price, 3),
        "unit": item.unit or "piece",
    }


async def _resolve_product_for_article(item, saas: MockSaasClient):
    """
    Returns either:
      - ("resolved", product_dict) for an exact/unambiguous match
      - ("ambiguous", product_dict) for a single fuzzy match needing confirmation
      - ("not_found", None) if nothing at all matched
    """
    matches = await saas.lookup_product(item.product_name)
    if len(matches) == 0:
        return "not_found", None
    if len(matches) == 1 and "_fuzzy_score" not in matches[0]:
        return "resolved", matches[0]
    if len(matches) == 1:
        return "ambiguous", matches[0]
    return "ambiguous_multiple", matches


async def _build_line_items_or_pause(articles: list, saas: MockSaasClient, session: SessionState, resume_intent: str, original_intent, language: str) -> tuple[list[dict] | None, VoiceResponse | None]:
    """
    Resolves products for each article in order. On the first ambiguous
    single-candidate match, stashes pending_disambiguation (kind="product")
    with everything already resolved so far, and returns (None, VoiceResponse).
    On full success, returns (line_items, None).
    """
    line_items: list[dict] = []

    for idx, item in enumerate(articles):
        status, result = await _resolve_product_for_article(item, saas)

        if status == "resolved":
            line_items.append(_line_item_from_product(item, result))
            continue

        if status == "not_found":
            line_items.append(_line_item_from_raw_name(item))
            continue

        if status == "ambiguous":
            names = f"{item.product_name} → {result['designation']}"
            session.pending_disambiguation = {
                "kind": "product",
                "candidate": result,
                "resume_intent": resume_intent,
                "original_intent": original_intent,
                "article_index": idx,
                "resolved_line_items": line_items,
            }
            question = t("client_confirm_single", language, names=names)
            return None, VoiceResponse(
                success=False,
                spoken_text=question,
                clarification_question=question,
                requires_confirmation=True,
                display_data=result,
            )

        names = ", ".join(p["designation"] for p in result)
        question = t("client_confirm_multiple", language, names=names)
        return None, VoiceResponse(
            success=False,
            spoken_text=question,
            clarification_question=question,
            display_data=result,
        )

    return line_items, None


async def _finalize_invoice_draft(intent: CreateInvoiceIntent, client: dict, saas: MockSaasClient, session: SessionState,
    line_items: list[dict] | None = None,
    ) -> VoiceResponse:
    if line_items is None:
        line_items, pause = await _build_line_items_or_pause(
            intent.articles, saas, session,
            resume_intent=IntentType.CREATE_INVOICE.value,
            original_intent=intent,
            language=intent.language,
        )
        if pause is not None:
            session.pending_disambiguation["resolved_client"] = client
            return pause

    draft = await saas.build_invoice_draft(
        client=client,
        line_items=line_items,
        currency=intent.currency,
        is_tva_applicable=intent.is_tva_applicable,
        is_stamp_applicable=intent.is_stamp_applicable,
        payment_method=intent.payment_method,
        terms_and_conditions=intent.terms_and_conditions,
        due_date=intent.due_date,
    )

    session.pending_draft = draft
    session.pending_confirmation = True
    session.last_intent = IntentType.CREATE_INVOICE.value
    session.awaiting_field = None
    session.pending_transcript = None
    session.pending_disambiguation = None

    return VoiceResponse(
        success=True,
        spoken_text=build_invoice_draft_spoken(draft, language=intent.language),
        requires_confirmation=True,
        draft_payload=draft,
    )


async def _create_invoice_draft(intent: CreateInvoiceIntent, saas: MockSaasClient, session: SessionState) -> VoiceResponse:
    result = await _resolve_single_client(
        intent.client_name, saas, intent.language, session, original_intent=intent
    )
    if isinstance(result, VoiceResponse):
        return result
    client = result

    missing_price_items = [item.product_name for item in intent.articles if item.unit_price is None]
    if missing_price_items:
        names = ", ".join(missing_price_items)
        question = t("missing_unit_price", intent.language, names=names)
        session.awaiting_field = "unit_price"
        session.awaiting_article_indices = [
            i for i, item in enumerate(intent.articles) if item.unit_price is None
        ]
        session.pending_transcript = intent.raw_transcript
        return VoiceResponse(
            success=False,
            spoken_text=question,
            clarification_question=question,
        )

    return await _finalize_invoice_draft(intent, client, saas, session)


async def _add_line_item(intent: AddLineItemIntent, saas: MockSaasClient, session: SessionState) -> VoiceResponse:
    if not intent.invoice_number:
        question = t("clarify_invoice_number", intent.language)
        session.awaiting_field = "invoice_number"
        session.awaiting_intent = intent
        session.pending_transcript = intent.raw_transcript
        return VoiceResponse(
            success=False,
            spoken_text=question,
            clarification_question=question,
        )

    if intent.unit_price is None:
        question = t("missing_unit_price", intent.language, names=intent.product_name)
        session.awaiting_field = "unit_price"
        session.awaiting_intent = intent         
        session.pending_transcript = intent.raw_transcript
        return VoiceResponse(
            success=False,
            spoken_text=question,
            clarification_question=question,
        )

    status, result = await _resolve_product_for_article(intent, saas)

    if status == "not_found":
        session.awaiting_field = "product_name"
        session.pending_transcript = intent.raw_transcript
        question = t("clarify_product_not_found", intent.language, name=intent.product_name)
        return VoiceResponse(
            success=False,
            spoken_text=question,
            clarification_question=question,
            error="product_not_found",
        )

    if status == "ambiguous":
        names = f"{intent.product_name} → {result['designation']}"
        session.pending_disambiguation = {
            "kind": "product",
            "candidate": result,
            "resume_intent": IntentType.ADD_LINE_ITEM.value,
            "original_intent": intent,
        }
        question = t("client_confirm_single", intent.language, names=names)
        return VoiceResponse(
            success=False,
            spoken_text=question,
            clarification_question=question,
            requires_confirmation=True,
            display_data=result,
        )

    if status == "ambiguous_multiple":
        names = ", ".join(p["designation"] for p in result)
        question = t("client_confirm_multiple", intent.language, names=names)
        return VoiceResponse(
            success=False,
            spoken_text=question,
            clarification_question=question,
            display_data=result,
        )

    designation = result["designation"]  

    return await _finalize_add_line_item(intent, designation, saas, session)


async def _finalize_add_line_item(intent: AddLineItemIntent, designation: str, saas: MockSaasClient, session: SessionState) -> VoiceResponse:
    existing_invoice = await saas.get_invoice(intent.invoice_number)
    if not existing_invoice:
        return VoiceResponse(
            success=False,
            spoken_text=t("invoice_not_found_number", intent.language, invoice_number=intent.invoice_number),
            error="invoice_not_found",
        )

    session.pending_line_item = {
        "invoice_number": intent.invoice_number,
        "designation": designation,
        "quantity": intent.quantity,
        "unit_price": intent.unit_price,
        "unit": intent.unit or "piece",
    }
    session.pending_confirmation = True
    session.last_intent = IntentType.ADD_LINE_ITEM.value
    session.awaiting_field = None
    session.pending_transcript = None
    session.pending_disambiguation = None

    qty_str = str(int(intent.quantity)) if intent.quantity == int(intent.quantity) else str(intent.quantity)
    prompt = (
        f"Ajouter {qty_str} {designation} ({intent.unit_price} {existing_invoice['currency']}/unité) "
        f"à la facture {intent.invoice_number} ? Dites 'confirme' ou 'annule'."
        if intent.language != "en" else
        f"Add {qty_str} {designation} ({intent.unit_price} {existing_invoice['currency']}/unit) "
        f"to invoice {intent.invoice_number}? Say 'confirm' or 'cancel'."
    )

    return VoiceResponse(
        success=False,
        spoken_text=prompt,
        clarification_question=None,
        requires_confirmation=True,
        draft_payload=session.pending_line_item,
    )


async def _resolve_disambiguation(session: SessionState, saas: MockSaasClient, language: str, accepted: bool) -> VoiceResponse:
    pending = session.pending_disambiguation
    session.pending_disambiguation = None

    if not accepted:
        original_intent = pending["original_intent"]
        if pending["kind"] == "client":
            session.awaiting_field = "client_name"
            session.pending_transcript = original_intent.raw_transcript
            question = t("clarify_client_rejected", language)
        else: 
            session.awaiting_field = "product_name"
            session.pending_transcript = original_intent.raw_transcript
            question = t("clarify_product_rejected", language)
        return VoiceResponse(
            success=False,
            spoken_text=question,
            clarification_question=question,
        )

    candidate = pending["candidate"]
    original_intent = pending["original_intent"]

    if pending["kind"] == "client":
        if isinstance(original_intent, CreateInvoiceIntent):
            missing_price_items = [
                item.product_name for item in original_intent.articles if item.unit_price is None
            ]
            if missing_price_items:
                names = ", ".join(missing_price_items)
                question = t("missing_unit_price", language, names=names)
                session.awaiting_field = "unit_price"
                session.pending_transcript = original_intent.raw_transcript
                return VoiceResponse(
                    success=False,
                    spoken_text=question,
                    clarification_question=question,
                )
            return await _finalize_invoice_draft(original_intent, candidate, saas, session)

        if isinstance(original_intent, LookupClientIntent):
            return VoiceResponse(
                success=True,
                spoken_text=build_client_spoken(candidate, language=language),
                display_data=candidate,
            )

    if pending["kind"] == "product":
        if pending["resume_intent"] == IntentType.ADD_LINE_ITEM.value:
            return await _finalize_add_line_item(original_intent, candidate["designation"], saas, session)

        if pending["resume_intent"] == IntentType.CREATE_INVOICE.value:
            resolved_client = pending.get("resolved_client")
            resolved_so_far = list(pending.get("resolved_line_items", []))
            article_idx = pending["article_index"]

            item = original_intent.articles[article_idx]
            resolved_so_far.append(_line_item_from_product(item, candidate))

            remaining = original_intent.articles[article_idx + 1:]
            if remaining:
                more_items, pause = await _build_line_items_or_pause(
                    remaining, saas, session,
                    resume_intent=IntentType.CREATE_INVOICE.value,
                    original_intent=original_intent,
                    language=language,
                )
                if pause is not None:
                    session.pending_disambiguation["resolved_line_items"] = (
                        resolved_so_far + session.pending_disambiguation["resolved_line_items"]
                    )
                    session.pending_disambiguation["article_index"] += article_idx + 1
                    session.pending_disambiguation["resolved_client"] = resolved_client
                    return pause
                resolved_so_far.extend(more_items)

            return await _finalize_invoice_draft(
                original_intent, resolved_client, saas, session, line_items=resolved_so_far
            )

    return VoiceResponse(
        success=False,
        spoken_text=t("unhandled_intent", language),
        error="unhandled_disambiguation",
    )

async def resume_awaiting_field(transcript: str, session: SessionState, saas: MockSaasClient, language: str):
    if session.awaiting_field not in ("unit_price", "invoice_number") or session.awaiting_intent is None:
        return None

    if session.awaiting_field == "invoice_number":
        intent = session.awaiting_intent
        normalized = normalize_invoice_number(transcript, saas.company_slug) if saas.company_slug else None

        if normalized is None:
            question = t("clarify_invoice_number", language)
            return VoiceResponse(
                success=False,
                spoken_text=question,
                clarification_question=question,
            )

        intent.invoice_number = normalized
        session.awaiting_field = None
        session.awaiting_intent = None
        session.pending_transcript = None
        return await dispatch(intent, saas, session)

    price = extract_price_only(transcript)
    if price is None:
        question = t("clarify_unit_price", language)
        return VoiceResponse(
            success=False,
            spoken_text=question,
            clarification_question=question,
        )

    intent = session.awaiting_intent

    if isinstance(intent, CreateInvoiceIntent):
        for idx in session.awaiting_article_indices:
            intent.articles[idx].unit_price = price

    elif isinstance(intent, AddLineItemIntent):
        intent.unit_price = price

    else:
        session.awaiting_field = None
        session.awaiting_intent = None
        session.awaiting_article_indices = None
        session.pending_transcript = None
        return VoiceResponse(
            success=False,
            spoken_text=t("unhandled_intent", language),
            error="unhandled_awaiting_intent_type",
        )

    session.awaiting_field = None
    session.awaiting_intent = None
    session.awaiting_article_indices = None
    session.pending_transcript = None

    return await dispatch(intent, saas, session)

    
async def _handle_confirm(session: SessionState, saas: MockSaasClient, language: str) -> VoiceResponse:
    if session.pending_disambiguation:
        return await _resolve_disambiguation(session, saas, language, accepted=True)

    if session.pending_line_item:
        item = session.pending_line_item
        session.pending_line_item = None
        session.pending_confirmation = False
        session.last_intent = None

        updated_invoice = await saas.add_line_item(
            invoice_number=item["invoice_number"],
            designation=item["designation"],
            quantity=item["quantity"],
            unit_price=item["unit_price"],
            unit=item["unit"],
        )
        if not updated_invoice:
            return VoiceResponse(
                success=False,
                spoken_text=t("invoice_not_found_number", language, invoice_number=item["invoice_number"]),
                error="invoice_not_found",
            )
        return VoiceResponse(
            success=True,
            spoken_text=build_line_item_added_spoken(
                item["invoice_number"], item["designation"], item["quantity"], language=language
            ),
            display_data=updated_invoice,
        )

    if not session.pending_confirmation or not session.pending_draft:
        return VoiceResponse(
            success=False,
            spoken_text=t("no_pending_confirmation", language),
            error="no_pending_confirmation",
        )

    invoice = await saas.confirm_invoice_draft(session.pending_draft)
    session.pending_draft = None
    session.pending_confirmation = False
    session.last_intent = None

    return VoiceResponse(
        success=True,
        spoken_text=t(
            "confirm_invoice_created", language,
            invoice_number=invoice["invoice_number"], client_name=invoice["client_name"],
            total_ttc=invoice["total_ttc"], currency=invoice["currency"],
        ),
        display_data=invoice,
    )


async def _handle_cancel(session: SessionState, saas: MockSaasClient, language: str) -> VoiceResponse:
    if session.pending_disambiguation:
        return await _resolve_disambiguation(session, saas, language, accepted=False)

    session.awaiting_field = None
    session.pending_transcript = None

    if session.pending_line_item:
        session.pending_line_item = None
        session.pending_confirmation = False
        session.last_intent = None
        return VoiceResponse(
            success=True,
            spoken_text=t("line_item_discarded", language),
        )

    if not session.pending_confirmation:
        return VoiceResponse(
            success=False,
            spoken_text=t("no_pending_cancellation", language),
            error="no_pending_confirmation",
        )

    session.pending_draft = None
    session.pending_confirmation = False
    session.last_intent = None

    return VoiceResponse(
        success=True,
        spoken_text=t("draft_discarded", language),
    )

def _clarification_prompt(intent) -> str:
    language = getattr(intent, "language", "en")

    if isinstance(intent, (ConfirmIntent, CancelIntent)):
        return t("clarify_confirm_or_cancel", language)

    fields = getattr(intent, "low_confidence_fields", [])

    if "invoice_number" in fields:
        inv = getattr(intent, "invoice_number", None)
        return (
            t("clarify_invoice_number_confirm", language, invoice_number=inv)
            if inv
            else t("clarify_invoice_number", language)
        )
    if "client_name" in fields:
        return t("clarify_client_name", language)
    if "unit_price" in fields:
        return t("clarify_unit_price", language)
    if "articles" in fields:
        return t("clarify_articles", language)

    return t("clarify_generic", language)