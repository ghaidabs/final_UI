def build_invoice_draft_spoken(draft: dict, language: str = "fr") -> str:
    item_count = len(draft.get("articles", []))
    total_ttc = draft.get("total_ttc", 0.0)
    currency = draft.get("currency", "TND")
    due_date = draft.get("due_date")

    if language == "en":
        client_name = draft.get("client_name", "the client")
        item_phrase = "1 item" if item_count == 1 else f"{item_count} items"
        due_phrase = f" Due by {due_date}." if due_date else ""
        return (
            f"Draft invoice for {client_name} with {item_phrase}, "
            f"total {total_ttc} {currency}.{due_phrase} "
            f"Say 'confirm' to create it, or 'cancel' to discard."
        )

    # default: fr
    client_name = draft.get("client_name", "le client")
    item_phrase = "1 article" if item_count == 1 else f"{item_count} articles"
    due_phrase = f" À payer avant le {due_date}." if due_date else ""
    return (
        f"Brouillon de facture pour {client_name} avec {item_phrase}, "
        f"total {total_ttc} {currency}.{due_phrase} "
        f"Dites 'confirme' pour la créer, ou 'annule' pour l'abandonner."
    )


def build_invoice_details_spoken(invoice: dict, language: str = "fr") -> str:
    if language == "en":
        return (
            f"Invoice {invoice.get('invoice_number')} for {invoice.get('client_name')}, "
            f"status: {invoice.get('status')}, "
            f"total: {invoice.get('total_ttc')} {invoice.get('currency')}."
        )

    return (
        f"Facture {invoice.get('invoice_number')} pour {invoice.get('client_name')}, "
        f"statut : {invoice.get('status')}, "
        f"total : {invoice.get('total_ttc')} {invoice.get('currency')}."
    )


def build_invoice_list_spoken(invoices: list[dict], language: str = "fr") -> str:
    if len(invoices) == 1:
        return build_invoice_details_spoken(invoices[0], language=language)

    numbers = ", ".join(i.get("invoice_number", "unknown") for i in invoices)

    if language == "en":
        return f"I found {len(invoices)} invoices: {numbers}. Which one would you like details on?"

    return f"J'ai trouvé {len(invoices)} factures : {numbers}. Sur laquelle voulez-vous des détails ?"


def build_line_item_added_spoken(
    invoice_number: str, designation: str, quantity: float, language: str = "fr"
) -> str:
    qty_str = str(int(quantity)) if quantity == int(quantity) else str(quantity)

    if language == "en":
        return f"Added {qty_str} of {designation} to invoice {invoice_number}."

    return f"{qty_str} {designation} ajouté(s) à la facture {invoice_number}."