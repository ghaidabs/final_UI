import json
from pathlib import Path
from copy import deepcopy
from datetime import datetime

DATA_DIR = Path(__file__).parent

def _load(filename):
    with open(DATA_DIR / filename, encoding="utf-8") as f:
        return json.load(f)

_clients   = {c["id"]: c for c in _load("clients.json")}
_products  = {p["id"]: p for p in _load("products.json")}
_invoices  = {i["invoice_number"]: i for i in _load("invoices.json")} 
_users     = {u["id"]: u for u in _load("users.json")}                 
_companies = {c["id"]: c for c in _load("companies.json")}            

_invoice_sequences: dict[str, int] = {}

def _next_invoice_number(company_id: int) -> str:
    slug = _companies[company_id]["slug"]
    month_key = datetime.now().strftime("%Y%m")       
    seq_key = f"{slug}_{month_key}"
    _invoice_sequences[seq_key] = _invoice_sequences.get(seq_key, 0) + 1
    seq = str(_invoice_sequences[seq_key]).zfill(3)
    return f"{slug}_F{month_key}-{seq}"               


def paginate(items: list, page: int = 1, size: int = 10) -> dict:
    total = len(items)
    pages = max(1, -(-total // size))                
    start = (page - 1) * size
    end = start + size
    return {
        "items": items[start:end],
        "total": total,
        "meta": {"total": total, "page": page, "size": size, "pages": pages},
        "stats": []
    }

def get_company_by_id(company_id: int) -> dict | None:
    return deepcopy(_companies.get(company_id))

def get_user_by_id(user_id: int) -> dict | None:
    return deepcopy(_users.get(user_id))


def get_all_clients(company_id: int, page: int = 1, size: int = 10) -> dict:
    items = [c for c in _clients.values() if c["company_id"] == company_id]
    return paginate([deepcopy(c) for c in items], page, size)


def get_client_by_id(client_id: int, company_id: int) -> dict | None:
    client = _clients.get(client_id)
    if client and client["company_id"] == company_id:
        return deepcopy(client)
    return None                                       


def search_clients_by_name(name: str, company_id: int) -> list:
    name_lower = name.lower()
    return [
        deepcopy(c) for c in _clients.values()
        if name_lower in f"{c['first_name']} {c['last_name']}".lower()
        and c["company_id"] == company_id             
    ]


def get_all_products(company_id: int, page: int = 1, size: int = 10) -> dict:
    items = [p for p in _products.values() if p["company_id"] == company_id]
    return paginate([deepcopy(p) for p in items], page, size)


def get_product_by_id(product_id: int, company_id: int) -> dict | None:
    product = _products.get(product_id)
    if product and product["company_id"] == company_id:
        return deepcopy(product)
    return None


def search_products_by_name(name: str, company_id: int) -> list:
    name_lower = name.lower()
    return [
        deepcopy(p) for p in _products.values()
        if name_lower in p["designation"].lower()
        and p["company_id"] == company_id
    ]


def get_all_invoices(company_id: int, page: int = 1, size: int = 10) -> dict:
    items = [i for i in _invoices.values() if i["company_id"] == company_id]
    return paginate([deepcopy(i) for i in items], page, size)


def get_invoice_by_number(invoice_number: str, company_id: int) -> dict | None:
    inv = _invoices.get(invoice_number)
    if inv and inv["company_id"] == company_id:
        return deepcopy(inv)
    return None


def get_invoices_by_client_name(client_name: str, company_id: int) -> list:
    name_lower = client_name.strip().lower()
    if not name_lower:
        return []                                     
    return [
        deepcopy(i) for i in _invoices.values()
        if name_lower in i["client_name"].lower()
        and i["company_id"] == company_id
    ]

def get_invoices_by_status(status: str, company_id: int) -> list:
    return [
        deepcopy(i) for i in _invoices.values()
        if i["status"] == status
        and i["company_id"] == company_id
    ]


def create_invoice(
    company_id: int,
    user_id: int,
    client: dict,
    line_items: list,
    currency: str = "TND",
    is_tva_applicable: bool = False,
    is_stamp_applicable: bool = False,
    payment_method: str | None = None,
    terms_and_conditions: str | None = None,
    ) -> dict:

        invoice_number = _next_invoice_number(company_id)
        now = datetime.now().isoformat()

        total_ht = round(sum(item["quantity"] * item["unit_price"] for item in line_items), 3)
        tva      = round(total_ht * 0.19, 3) if is_tva_applicable else 0.0
        stamp    = 1.0 if is_stamp_applicable else 0.0
        total_ttc = round(total_ht + tva + stamp, 3)

        invoice = {
            "id": max((i["id"] for i in _invoices.values()), default=0) + 1,
            "invoice_number": invoice_number,
            "date_issued": now,
            "status": "draft",
            "user_id": user_id,
            "company_id": company_id,
            "articles": line_items,
            "commerce_inter_product_infos": [],
            "client_name": f"{client['first_name']} {client['last_name']}",
            "client_address": client["address"],
            "client_matricule_fiscale": client["mat_fiscale"],
            "currency": currency,
            "invoice_date": now,
            "is_tva_applicable": is_tva_applicable,
            "is_stamp_applicable": is_stamp_applicable,
            "total_ht": total_ht,
            "tva": tva,
            "total_ttc": total_ttc,
            "fret_fob": 0.0,
            "fret_out": 0.0,
            "terms_and_conditions": terms_and_conditions,
            "payment_method": payment_method,
            "display_discount": False
        }

        _invoices[invoice_number] = invoice
        return deepcopy(invoice)


def build_invoice_draft(
    company_id: int,
    user_id: int,
    client: dict,
    line_items: list,
    currency: str = "TND",
    is_tva_applicable: bool = False,
    is_stamp_applicable: bool = False,
    payment_method: str | None = None,
    terms_and_conditions: str | None = None,
    ) -> dict:
        now = datetime.now().isoformat()

        total_ht = round(sum(item["quantity"] * item["unit_price"] for item in line_items), 3)
        tva      = round(total_ht * 0.19, 3) if is_tva_applicable else 0.0
        stamp    = 1.0 if is_stamp_applicable else 0.0
        total_ttc = round(total_ht + tva + stamp, 3)

        return {
            "invoice_number": None,
            "date_issued": now,
            "status": "draft",
            "user_id": user_id,
            "company_id": company_id,
            "articles": line_items,
            "commerce_inter_product_infos": [],
            "client_name": f"{client['first_name']} {client['last_name']}",
            "client_address": client["address"],
            "client_matricule_fiscale": client["mat_fiscale"],
            "currency": currency,
            "invoice_date": now,
            "is_tva_applicable": is_tva_applicable,
            "is_stamp_applicable": is_stamp_applicable,
            "total_ht": total_ht,
            "tva": tva,
            "total_ttc": total_ttc,
            "fret_fob": 0.0,
            "fret_out": 0.0,
            "terms_and_conditions": terms_and_conditions,
            "payment_method": payment_method,
            "display_discount": False,
        }

def confirm_invoice_draft(draft: dict) -> dict:
    company_id = draft["company_id"]
    invoice_number = _next_invoice_number(company_id)

    invoice = {**draft, "invoice_number": invoice_number, "status": "validated"}
    invoice["id"] = max((i["id"] for i in _invoices.values()), default=0) + 1

    _invoices[invoice_number] = invoice
    return deepcopy(invoice)


def add_line_item(
    invoice_number: str,
    company_id: int,
    designation: str,
    quantity: float,
    unit_price: float,
    unit: str,
    description: str | None = None,
    ) -> dict | None:
        inv = _invoices.get(invoice_number)
        if not inv:
            return None
        if inv["company_id"] != company_id:
            return None

        existing = next(
            (a for a in inv["articles"] if a["designation"] == designation),
            None,
        )

        if existing:
            existing["quantity"] += quantity
            existing["unit_price"] = unit_price
            existing["total_ht"] = round(existing["quantity"] * existing["unit_price"], 3)
            if description:
                existing["description"] = description
        else:
            new_item = {
                "name": designation,
                "designation": designation,
                "description": description or "",
                "quantity": quantity,
                "unit_price": unit_price,
                "total_ht": round(quantity * unit_price, 3),
                "unit": unit
            }
            inv["articles"].append(new_item)

        inv["total_ht"]  = round(sum(a["total_ht"] for a in inv["articles"]), 3)
        inv["tva"]       = round(inv["total_ht"] * 0.19, 3) if inv["is_tva_applicable"] else 0.0
        stamp            = 1.0 if inv["is_stamp_applicable"] else 0.0
        inv["total_ttc"] = round(inv["total_ht"] + inv["tva"] + stamp, 3)

        return deepcopy(inv)