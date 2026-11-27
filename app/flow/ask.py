"""'Ask the shop': three fixed questions, answered by plain queries. The AI only picks which one; it never makes up
an answer."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from app.domain.catalog import Catalog
from app.domain.khata import balance
from app.domain.order import describe
from app.store.db import Store


@dataclass
class Answer:
    kind: str
    facts: dict


def _name(catalog: Catalog, code: str) -> str:
    item = catalog.get(code)
    return item.name if item else code


def to_ship(store: Store, catalog: Catalog) -> Answer:
    rows = []
    for o in store.orders_in_states(["open", "billed"]):
        bill = store.bill_for_order(o.id)
        rows.append({"customer": o.customer_name, "bill_number": bill["number"] if bill else None,
                     "lines": len(o.lines), "total_paise": sum(l.quantity * l.rate_paise for l in o.lines)})
    return Answer("to_ship", {"orders": rows})


def customer_summary(store: Store, catalog: Catalog, customer_id: int) -> Answer:
    order = store.open_order_for_customer(customer_id)
    lines = [{"item": _name(catalog, l.item_code), "qty": describe(l)} for l in order.lines] if order else []
    return Answer("customer_summary", {"customer": store.customer_name(customer_id), "open_lines": lines,
                                       "balance_paise": balance(store.ledger_for(customer_id))})


def item_count(store: Store, catalog: Catalog, item_code: str, now: datetime, days: int = 7) -> Answer:
    since = (now - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")
    return Answer("item_count", {"item": _name(catalog, item_code),
                                 "quantity": store.item_quantity_since(item_code, since), "days": days})
