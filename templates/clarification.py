from typing import Any

DEFAULT_LANGUAGE = "fr"

_STRINGS: dict[str, dict[str, str]] = {
    "en": {
        "client_not_found": "No client found matching '{client_name}'.",
        "client_confirm_single": "Did you mean {names}? Please confirm.",
        "client_confirm_multiple": (
            "I found several clients matching that name: {names}. Which one did you mean?"
        ),
        "invoice_or_client_missing": "Which invoice number or client did you mean?",
        "invoice_not_found": "I couldn't find any matching invoices.",
        "invoice_not_found_number": "I couldn't find invoice {invoice_number}.",
        "missing_unit_price": "I didn't catch the price for {names}. What's the unit price?",
        "confirm_invoice_created": (
            "Invoice {invoice_number} has been created for {client_name}, "
            "total {total_ttc} {currency}."
        ),
        "no_pending_confirmation": "There's nothing waiting to be confirmed right now.",
        "no_pending_cancellation": "There's nothing waiting to be cancelled right now.",
        "draft_discarded": "Okay, I discarded the draft invoice.",
        "unknown_intent": "I didn't understand that. Could you rephrase?",
        "unhandled_intent": "Sorry, an unsupported intent was received.",
        "clarify_confirm_or_cancel": "Sorry, were you confirming or cancelling that? Could you repeat?",
        "clarify_invoice_number_confirm": "Did you mean invoice {invoice_number}? Please confirm.",
        "clarify_invoice_number": "Which invoice number did you mean?",
        "clarify_client_name": "I wasn't sure about the client name. Could you repeat it?",
        "clarify_unit_price": "I wasn't sure about the price. Could you confirm the amount?",
        "clarify_articles": "I wasn't sure about one of the items or amounts. Could you repeat that part?",
        "clarify_generic": "I wasn't sure I caught that correctly. Could you repeat?",
        "clarify_client_rejected": "Okay, who did you mean instead?",
        "clarify_product_rejected": "Okay, which product or service did you mean instead?",
        "clarify_product_not_found": "I couldn't find a product called '{name}' in your catalog. Which product did you mean?",
        "line_item_discarded": "Okay, I discarded that line item.",
    },
    "fr": {
        "client_not_found": "Aucun client trouvé correspondant à « {client_name} ».",
        "client_confirm_single": "Vous vouliez dire {names} ? Merci de confirmer.",
        "client_confirm_multiple": (
            "J'ai trouvé plusieurs clients correspondant à ce nom : {names}. "
            "Lequel vouliez-vous dire ?"
        ),
        "invoice_or_client_missing": "Quel numéro de facture ou quel client vouliez-vous dire ?",
        "invoice_not_found": "Je n'ai trouvé aucune facture correspondante.",
        "invoice_not_found_number": "Je n'ai pas trouvé la facture {invoice_number}.",
        "missing_unit_price": "Je n'ai pas compris le prix pour {names}. Quel est le prix unitaire ?",
        "confirm_invoice_created": (
            "La facture {invoice_number} a été créée pour {client_name}, "
            "total {total_ttc} {currency}."
        ),
        "no_pending_confirmation": "Il n'y a rien à confirmer pour le moment.",
        "no_pending_cancellation": "Il n'y a rien à annuler pour le moment.",
        "draft_discarded": "D'accord, j'ai supprimé le brouillon de facture.",
        "unknown_intent": "Je n'ai pas compris. Pouvez-vous reformuler ?",
        "unhandled_intent": "Désolé, une intention non prise en charge a été reçue.",
        "clarify_confirm_or_cancel": "Désolé, souhaitiez-vous confirmer ou annuler ? Pouvez-vous répéter ?",
        "clarify_invoice_number_confirm": "Vous vouliez dire la facture {invoice_number} ? Merci de confirmer.",
        "clarify_invoice_number": "Quel numéro de facture vouliez-vous dire ?",
        "clarify_client_name": "Je n'étais pas sûr du nom du client. Pouvez-vous le répéter ?",
        "clarify_unit_price": "Je n'étais pas sûr du prix. Pouvez-vous confirmer le montant ?",
        "clarify_articles": (
            "Je n'étais pas sûr d'un des articles ou montants. Pouvez-vous répéter cette partie ?"
        ),
        "clarify_generic": "Je n'étais pas sûr d'avoir bien compris. Pouvez-vous répéter ?",
        "clarify_client_rejected": "D'accord, qui vouliez-vous dire alors ?",
        "clarify_product_rejected": "D'accord, quel produit ou service vouliez-vous dire ?",
        "clarify_product_not_found": "Je n'ai trouvé aucun produit appelé « {name} » dans votre catalogue. Quel produit vouliez-vous dire ?",
        "line_item_discarded": "D'accord, j'ai annulé cet ajout d'article.",
    },
}


def t(key: str, language: str | None, **kwargs: Any) -> str:
    lang = language if language in _STRINGS else DEFAULT_LANGUAGE
    template = _STRINGS[lang].get(key) or _STRINGS[DEFAULT_LANGUAGE].get(key, key)
    return template.format(**kwargs)