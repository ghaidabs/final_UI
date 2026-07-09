def build_payment_status_spoken(invoices: list[dict], language: str = "fr") -> str:
    if len(invoices) == 1:
        inv = invoices[0]
        status = inv.get("status", "unknown")

        if language == "en":
            if status == "paid":
                return f"Invoice {inv['invoice_number']} has been paid."
            elif status == "draft":
                return f"Invoice {inv['invoice_number']} is still a draft and hasn't been sent."
            elif status in ("cancelled", "canceled", "void"):
                return f"Invoice {inv['invoice_number']} was cancelled."
            else:
                return f"Invoice {inv['invoice_number']} is {status}, not yet paid."

        # fr
        if status == "paid":
            return f"La facture {inv['invoice_number']} a été payée."
        elif status == "draft":
            return f"La facture {inv['invoice_number']} est encore un brouillon et n'a pas été envoyée."
        elif status in ("cancelled", "canceled", "void"):
            return f"La facture {inv['invoice_number']} a été annulée."
        else:
            return f"La facture {inv['invoice_number']} est {status}, pas encore payée."

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