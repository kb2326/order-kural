"""Shop actions after an order is confirmed: the GST tax invoice, payments into the khata, shipping and undo."""
from __future__ import annotations

import json
from dataclasses import asdict
from datetime import date
from pathlib import Path

from app.domain.bill import (STATE_NAMES, Invoice, InvoiceLine, make_invoice, packing_list, share_text,
                             tax_lines)
from app.domain.catalog import Catalog
from app.domain.khata import balance
from app.domain.money import format_inr
from app.domain.order import Order
from app.domain.rules import Payment
from app.store.db import Store


SHOP_FILE = Path(__file__).parent.parent.parent / "data" / "shop.json"


def load_shop() -> dict:
    """The selling shop's own details (made-up demo values in data/shop.json)."""
    return json.loads(SHOP_FILE.read_text(encoding="utf-8"))


class ShopError(Exception):
    """A shop action that cannot be done; the message is safe to say to the owner."""


class ShopService:
    def __init__(self, store: Store, catalog: Catalog, shop: dict | None = None):
        self.store = store
        self.catalog = catalog
        self.shop = shop or load_shop()

    def _on_billed(self, inv: Invoice, customer_id: int) -> None:
        self.store.add_ledger(customer_id=customer_id, kind="bill", amount_paise=inv.grand_total_paise,
                              ref_bill=inv.number)

    def preview_invoice(self, order: Order) -> Invoice:
        """The invoice this order would get now (for the read-back before "sari"); raises ShopError if it can't."""
        if not order.lines:
            raise ShopError(f"Nothing to bill for {order.customer_name}")
        try:
            return make_invoice(order, self.catalog, self.shop, self.store.next_bill_number(),
                                date.today().isoformat())
        except ValueError as e:
            raise ShopError(str(e)) from e

    def bill_view(self, number: int) -> dict | None:
        """Everything the invoice page and the share button need, from the stored (frozen) invoice."""
        row = self.store.get_bill(number)
        if row is None:
            return None
        order = self.store.get_order(row["order_id"])
        data = json.loads(row["lines_json"])
        inv = Invoice(**{**data, "lines": [InvoiceLine(**l) for l in data["lines"]]})
        money = {k: format_inr(getattr(inv, k)) for k in ("taxable_paise", "cgst_paise", "sgst_paise", "igst_paise",
                                                           "round_off_paise", "grand_total_paise")}
        return {**asdict(inv), "money": money, "voided": bool(row["voided"]), "order_state": order.state,
                "place_of_supply_name": STATE_NAMES.get(inv.place_of_supply, inv.place_of_supply),
                "tax_lines": [{"label": n, "amount": format_inr(p)} for n, p in tax_lines(inv)],
                "lines": [{**asdict(l), "rate": format_inr(l.rate_paise), "amount": format_inr(l.amount_paise)}
                          for l in inv.lines],
                "packing": [{"item": i, "size": s, "qty": q} for i, s, q in packing_list(order, self.catalog)],
                "shop": self.shop, "share_text": share_text(inv, self.shop),
                "customer": inv.buyer_name, "total": format_inr(inv.grand_total_paise)}

    def balance(self, customer_id: int) -> int:
        return balance(self.store.ledger_for(customer_id))

    def record_payment(self, customer_id: int, amount_paise: int, mode: Payment) -> int:
        """Returns the new balance (negative = advance paid)."""
        if amount_paise <= 0:
            raise ShopError("Payment amount must be more than zero")
        with self.store.tx():
            self.store.add_ledger(customer_id=customer_id, kind="payment", amount_paise=amount_paise, mode=mode)
            return self.balance(customer_id)

    def mark_shipped(self, order_id: int, transport: str | None) -> None:
        with self.store.tx():
            order = self.store.get_order(order_id)
            if order is None or order.state not in ("open", "billed"):
                raise ShopError("No order waiting to ship")
            if transport:
                self.store.set_order_transport(order_id, transport)
            self.store.set_order_state(order_id, "shipped")

    def undo_last(self, customer_id: int) -> str:
        """Reverse the latest bill or payment that is not already reversed (tap only, never by voice)."""
        with self.store.tx():
            entries = self.store.ledger_for(customer_id)
            reversed_ids = {e["reverses"] for e in entries if e["kind"] == "reversal"}
            target = next((e for e in reversed(entries)
                           if e["kind"] != "reversal" and e["id"] not in reversed_ids), None)
            if target is None:
                raise ShopError("Nothing to undo")
            self.store.add_ledger(customer_id=customer_id, kind="reversal", amount_paise=target["amount_paise"],
                                  reverses=target["id"])
            if target["kind"] == "bill":
                bill = self.store.get_bill(target["ref_bill"])
                self.store.set_bill_voided(bill["number"])
                self.store.set_order_state(bill["order_id"], "open")
                return f"Bill {bill['number']} undone"
            return f"Payment of {format_inr(target['amount_paise'])} undone"

    def issue_bill(self, order_id: int) -> Invoice:
        with self.store.tx():
            order = self.store.get_order(order_id)
            if order is None:
                raise ShopError("No such order")
            if order.state != "open":
                raise ShopError(f"Order for {order.customer_name} is already {order.state}")
            inv = self.preview_invoice(order)
            customer_id = self.store.customer_id_of_order(order_id)
            self.store.save_bill(number=inv.number, order_id=order_id, customer_id=customer_id,
                                 total_paise=inv.grand_total_paise,
                                 lines_json=json.dumps(asdict(inv), ensure_ascii=False))
            self.store.set_order_state(order_id, "billed")
            self._on_billed(inv, customer_id)
        return inv
