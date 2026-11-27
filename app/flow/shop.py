"""Shop actions after an order is confirmed: bill it, and (Task 6) payments, shipping and undo."""
from __future__ import annotations

import json
from dataclasses import asdict
from datetime import date

from app.domain.bill import Bill, make_bill
from app.domain.catalog import Catalog
from app.store.db import Store


class ShopError(Exception):
    """A shop action that cannot be done; the message is safe to say to the owner."""


class ShopService:
    def __init__(self, store: Store, catalog: Catalog):
        self.store = store
        self.catalog = catalog

    def _on_billed(self, bill: Bill, customer_id: int) -> None:
        """Seam for the khata debit (Task 6)."""

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
