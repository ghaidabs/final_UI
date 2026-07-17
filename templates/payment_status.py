from templates.spoken_format import spoken_invoice_suffix

def build_payment_status_spoken(invoices: list[dict], language: str = "fr") -> str:
    if len(invoices) == 1:
        inv = invoices[0]
        status = inv.get("status", "unknown")
        number = spoken_invoice_suffix(inv["invoice_number"], language=language)

        if language == "en":
            if status == "paid":
                return f"Invoice {number} has been paid."
            elif status == "draft":
                return f"Invoice {number} is still a draft and hasn't been sent."
            elif status in ("cancelled", "canceled", "void"):
                return f"Invoice {number} was cancelled."
            else:
                return f"Invoice {number} is {status}, not yet paid."

        # fr
        if status == "paid":
            return f"La facture {number} a été payée."
        elif status == "draft":
            return f"La facture {number} est encore un brouillon et n'a pas été envoyée."
        elif status in ("cancelled", "canceled", "void"):
            return f"La facture {number} a été annulée."
        else:
            return f"La facture {number} est {status}, pas encore payée."

    unpaid = [i for i in invoices if i.get("status") not in ("paid",)]
    paid = [i for i in invoices if i.get("status") == "paid"]

    if language == "en":
        return (
            f"Found {len(invoices)} invoices: {len(paid)} paid, "
            f"{len(unpaid)} not yet paid."
        )

    return (
        f"J'ai trouvé {len(invoices)} factures : {len(paid)} payées, "
        f"{len(unpaid)} pas encore payées."
    )

def build_payment_status_display(invoices: list[dict], language: str = "fr") -> str:
    if len(invoices) == 1:
        inv = invoices[0]
        status = inv.get("status", "unknown")
        number = inv["invoice_number"]

        if language == "en":
            if status == "paid":
                return f"Invoice {number} has been paid."
            elif status == "draft":
                return f"Invoice {number} is still a draft and hasn't been sent."
            elif status in ("cancelled", "canceled", "void"):
                return f"Invoice {number} was cancelled."
            else:
                return f"Invoice {number} is {status}, not yet paid."

        # fr
        if status == "paid":
            return f"La facture {number} a été payée."
        elif status == "draft":
            return f"La facture {number} est encore un brouillon et n'a pas été envoyée."
        elif status in ("cancelled", "canceled", "void"):
            return f"La facture {number} a été annulée."
        else:
            return f"La facture {number} est {status}, pas encore payée."

    unpaid = [i for i in invoices if i.get("status") not in ("paid",)]
    paid = [i for i in invoices if i.get("status") == "paid"]

    if language == "en":
        return (
            f"{len(invoices)} invoices: {len(paid)} paid, "
            f"{len(unpaid)} not yet paid."
        )

    return (
        f"{len(invoices)} factures : {len(paid)} payées, "
        f"{len(unpaid)} pas encore payées."
    )