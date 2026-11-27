"""Shop actions after an order is confirmed: bill it, and (Task 6) payments, shipping and undo."""
from __future__ import annotations

import json
from dataclasses import asdict
from datetime import date

from app.domain.bill import Bill, BillLine, make_bill, share_text
from app.domain.catalog import Catalog
from app.domain.khata import balance
from app.domain.money import format_inr
from app.domain.rules import Payment
from app.store.db import Store


class ShopError(Exception):
    """A shop action that cannot be done; the message is safe to say to the owner."""


class ShopService:
    def __init__(self, store: Store, catalog: Catalog):
        self.store = store
        self.catalog = catalog

    def _on_billed(self, bill: Bill, customer_id: int) -> None:
        self.store.add_ledger(customer_id=customer_id, kind="bill", amount_paise=bill.total_paise,
                              ref_bill=bill.number)

    def bill_view(self, number: int) -> dict | None:
        """Everything the bill page and the share button need, from the stored (frozen) bill."""
        row = self.store.get_bill(number)
        if row is None:
            return None
        order = self.store.get_order(row["order_id"])
        lines = [BillLine(**l) for l in json.loads(row["lines_json"])]
        bill = Bill(number=number, order_id=row["order_id"], customer_name=order.customer_name, city=order.city,
                    transport=order.transport, payment=order.payment, lines=lines, total_paise=row["total_paise"],
                    created_at=row["created_at"][:10])
        packing = []  # qty_text is "S 6, M 6" for sized lines (labels may contain spaces) or just "24"
        for l in lines:
            if l.qty_text.isdigit():
                packing.append({"item": l.name, "size": "-", "qty": l.quantity})
                continue
            for part in l.qty_text.split(", "):
                size, _, qty = part.rpartition(" ")
                packing.append({"item": l.name, "size": size, "qty": int(qty)})
        return {"number": number, "customer": bill.customer_name, "city": bill.city, "date": bill.created_at,
                "transport": bill.transport, "payment": bill.payment, "voided": bool(row["voided"]),
                "order_state": order.state, "total_paise": bill.total_paise, "total": format_inr(bill.total_paise),
                "lines": [{**asdict(l), "rate": format_inr(l.rate_paise), "amount": format_inr(l.amount_paise)}
                          for l in lines],
                "packing": packing, "share_text": share_text(bill)}

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

    def issue_bill(self, order_id: int) -> Bill:
        with self.store.tx():
            order = self.store.get_order(order_id)
            if order is None:
                raise ShopError("No such order")
            if order.state != "open":
                raise ShopError(f"Order for {order.customer_name} is already {order.state}")
            if not order.lines:
                raise ShopError(f"Nothing to bill for {order.customer_name}")
            bill = make_bill(order, self.catalog, self.store.next_bill_number(), date.today().isoformat())
            customer_id = self.store.customer_id_of_order(order_id)
            self.store.save_bill(number=bill.number, order_id=order_id, customer_id=customer_id,
                                 total_paise=bill.total_paise,
                                 lines_json=json.dumps([asdict(l) for l in bill.lines], ensure_ascii=False))
            self.store.set_order_state(order_id, "billed")
            self._on_billed(bill, customer_id)
        return bill
