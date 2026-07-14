from mock.db import (
    search_clients_by_name, get_client_by_id,
    search_products_by_name, get_product_by_id,
    get_invoice_by_number, get_invoices_by_client_name, get_invoices_by_status,
    create_invoice, add_line_item,
    build_invoice_draft, confirm_invoice_draft, get_all_products, get_all_clients
)
from agent.normalizer import normalize_invoice_number
from agent.fuzzy import find_fuzzy
from rag.indexer import ensure_client_index, ensure_product_index
from rag.retriever import find_similar
import asyncio


class MockSaasClient:
    def __init__(self, company_id: int, user_id: int, company_slug: str | None = None):
        self.company_id = company_id
        self.user_id = user_id
        self.company_slug = company_slug


    async def lookup_client(self, name: str) -> list[dict]:
        exact = search_clients_by_name(name, self.company_id)
        if exact:
            return exact

        all_clients = get_all_clients(self.company_id, page=1, size=10_000)["items"]
        fuzzy = find_fuzzy(name, all_clients, lambda c: f"{c['first_name']} {c['last_name']}")
        if fuzzy:
            return fuzzy

        await asyncio.to_thread(ensure_client_index, self.company_id)
        candidates = await asyncio.to_thread(find_similar, "client", self.company_id, name, 3)
        return [
            {**c, "_fuzzy_score": cand["score"]}
            for cand in candidates
            if (c := get_client_by_id(cand["id"], self.company_id))
        ]

    async def get_client(self, client_id: int) -> dict | None:
        return get_client_by_id(client_id, self.company_id)


    async def lookup_product(self, name: str) -> list[dict]:
        exact = search_products_by_name(name, self.company_id)
        if exact:
            return exact

        all_products = get_all_products(self.company_id, page=1, size=10_000)["items"]
        fuzzy = find_fuzzy(name, all_products, lambda p: p["designation"])
        if fuzzy:
            return fuzzy

        await asyncio.to_thread(ensure_product_index, self.company_id)
        candidates = await asyncio.to_thread(find_similar, "product", self.company_id, name, 3)
        return [
            {**p, "_fuzzy_score": cand["score"]}
            for cand in candidates
            if (p := get_product_by_id(cand["id"], self.company_id))
        ]

    async def get_product(self, product_id: int) -> dict | None:
        return get_product_by_id(product_id, self.company_id)


    async def get_invoice(self, invoice_number: str) -> dict | None:
        if self.company_slug:
            invoice_number = normalize_invoice_number(invoice_number, self.company_slug) or invoice_number
        return get_invoice_by_number(invoice_number, self.company_id)

    async def get_invoices_by_client(self, client_name: str) -> list[dict]:
        return get_invoices_by_client_name(client_name, self.company_id)

    async def get_invoices_by_status(self, status: str) -> list[dict]:
        return get_invoices_by_status(status, self.company_id)

    async def create_invoice(
        self,
        client: dict,
        line_items: list[dict],
        currency: str = "TND",
        is_tva_applicable: bool = False,
        is_stamp_applicable: bool = False,
        payment_method: str | None = None,
        terms_and_conditions: str | None = None,
        ) -> dict:
            return create_invoice(
                company_id=self.company_id,
                user_id=self.user_id,
                client=client,
                line_items=line_items,
                currency=currency,
                is_tva_applicable=is_tva_applicable,
                is_stamp_applicable=is_stamp_applicable,
                payment_method=payment_method,
                terms_and_conditions=terms_and_conditions,
            )

    async def build_invoice_draft(self, client: dict, line_items: list, **kwargs) -> dict:
        return build_invoice_draft(
            company_id=self.company_id,
            user_id=self.user_id,
            client=client,
            line_items=line_items,
            **kwargs,
        )

    async def confirm_invoice_draft(self, draft: dict) -> dict:
        return confirm_invoice_draft(draft)

        
    async def add_line_item(self, invoice_number: str, designation: str, quantity: float,
                             unit_price: float, unit: str, description: str | None = None) -> dict | None:
        if self.company_slug:
            invoice_number = normalize_invoice_number(invoice_number, self.company_slug) or invoice_number
        return add_line_item(invoice_number=invoice_number, company_id=self.company_id,
                              designation=designation, quantity=quantity, unit_price=unit_price,
                              unit=unit, description=description)