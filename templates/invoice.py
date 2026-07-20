from templates.spoken_format import spoken_amount, status_phrase, spoken_invoice_suffix, display_amount

def build_invoice_draft_spoken(draft: dict, language: str = "fr") -> str:
    item_count = len(draft.get("articles", []))

    if language == "en":
        client_name = draft.get("client_name", "the client")
        return (
            f"Here's the draft invoice for {client_name}. "
            f"Please 'confirm' to create it, or 'cancel' to discard it."
        )

    client_name = draft.get("client_name", "le client")
    return (
        f"Voici le brouillon de facture pour {client_name}. "
        f"Merci de 'confirmer' pour la créer, ou 'annuler' pour l'abandonner."
    )


def build_invoice_details_spoken(invoice: dict, language: str = "fr") -> str:
    number = spoken_invoice_suffix(invoice.get("invoice_number"), language=language)
    client_name = invoice.get("client_name")
    amount = spoken_amount(invoice.get("total_ttc"), invoice.get("currency", "TND"), language)
    phrase = status_phrase(invoice.get("status"), language)

    if language == "en":
        return (
            f"The invoice {number} for {client_name} {phrase}. "
            f"The total amount is {amount}."
        )

    return (
        f"La facture {number} pour {client_name} {phrase}. "
        f"Le montant total est de {amount}."
    )


def build_invoice_list_spoken(invoices: list[dict], language: str = "fr") -> str:
    if len(invoices) == 1:
        return build_invoice_details_spoken(invoices[0], language=language)

    numbers = " ; ".join(
        spoken_invoice_suffix(i.get("invoice_number"), language=language) or "unknown"
        for i in invoices
    )

    if language == "en":
        return f"I found {len(invoices)} invoices: {numbers}. Which one would you like details on?"

    return f"J'ai trouvé {len(invoices)} factures : {numbers}. Sur laquelle voulez-vous des détails ?"


def build_line_item_added_spoken(invoice_number: str, designation: str, quantity: float, language: str = "fr") -> str:
    number = spoken_invoice_suffix(invoice_number, language=language)
    qty_str = str(int(quantity)) if quantity == int(quantity) else str(quantity)

    if language == "en":
        return f"Done — added {qty_str} of {designation} to invoice {number}."

    return f"C'est fait — {qty_str} {designation} ajouté(s) à la facture {number}."


def build_line_item_confirmation_spoken(invoice_number: str, designation: str, quantity: float, unit_price: float, currency: str, language: str = "fr") -> str:
    number = spoken_invoice_suffix(invoice_number, language=language)
    qty_str = str(int(quantity)) if quantity == int(quantity) else str(quantity)
    unit_price_str = spoken_amount(unit_price, currency, language)

    if language == "en":
        return (
            f"We will add {qty_str} {designation} at {unit_price_str} each "
            f"to invoice {number}? Please 'confirm' or 'cancel'."
        )

    return (
        f"On va ajouter {qty_str} {designation} à {unit_price_str} l'unité "
        f"à la facture {number} ? Merci de 'confirmer' ou 'annuler'."
    )


def build_invoice_details_display(invoice: dict, language: str = "fr") -> str:
    number = invoice.get("invoice_number")
    client_name = invoice.get("client_name")
    amount = display_amount(invoice.get("total_ttc"), invoice.get("currency", "TND"))
    phrase = status_phrase(invoice.get("status"), language)
    
    if language == "en":
        return f"Invoice {number} for {client_name} {phrase}. Total: {amount}."
    
    return f"La facture {number} pour {client_name} {phrase}. Total : {amount}."


def build_invoice_draft_display(draft: dict, language: str = "fr") -> str:
    client_name = draft.get("client_name") or ("the client" if language == "en" else "le client")
    amount = display_amount(draft.get("total_ttc"), draft.get("currency", "TND"))

    if language == "en":
        return (
            f"Draft invoice for {client_name} — total {amount}. "
            f"Confirm or cancel."
        )
    return (
        f"Brouillon de facture pour {client_name} — total {amount}. "
        f"Confirmez ou annulez."
    )


def build_invoice_list_display(invoices: list[dict], language: str = "fr") -> str:
    if len(invoices) == 1:
        return build_invoice_details_display(invoices[0], language=language)
    
    numbers = " ; ".join(i.get("invoice_number") or "?" for i in invoices)
    
    if language == "en":
        return f"Found {len(invoices)} invoices: {numbers}."

    return f"{len(invoices)} factures trouvées : {numbers}."


def build_line_item_added_display(invoice_number: str, designation: str, quantity: float, language: str = "fr") -> str:
    number = invoice_number
    qty_str = str(int(quantity)) if quantity == int(quantity) else str(quantity)

    if language == "en":
        return f"Added {qty_str} of {designation} to invoice {number}."

    return f"{qty_str} {designation} ajouté(s) à la facture {number}."


def build_line_item_confirmation_display(invoice_number: str, designation: str, quantity: float, unit_price: float, currency: str, language: str = "fr") -> str:
    number = invoice_number
    qty_str = str(int(quantity)) if quantity == int(quantity) else str(quantity)
    unit_price_str = display_amount(unit_price, currency)

    if language == "en":
        return f"We will add {qty_str} {designation} at {unit_price_str} each to invoice {number}? Confirm or cancel."

    return f"On va ajouter {qty_str} {designation} à {unit_price_str} l'unité à la facture {number} ? Confirmez ou annulez."