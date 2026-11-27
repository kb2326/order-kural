"""The order bill (an estimate, not a GST invoice: the auditor does tax monthly) and the packing list for staff."""
from __future__ import annotations

from dataclasses import dataclass

from app.domain.catalog import Catalog
from app.domain.money import format_inr
from app.domain.order import Order, describe

TITLE = "Order bill (estimate)"
FOOTER = "Tax as per final invoice"


@dataclass(frozen=True)
class BillLine:
    item_code: str
    name: str
    hsn: str
    qty_text: str
    quantity: int
    rate_paise: int
    amount_paise: int


@dataclass(frozen=True)
class Bill:
    number: int
    order_id: int
    customer_name: str
    city: str | None
    transport: str | None
    payment: str | None
    lines: list[BillLine]
    total_paise: int
    created_at: str


def make_bill(order: Order, catalog: Catalog, number: int, created_at: str) -> Bill:
    lines = []
    for l in order.lines:
        item = catalog.get(l.item_code)
        lines.append(BillLine(item_code=l.item_code, name=item.name if item else l.item_code,
                              hsn=item.hsn if item else "", qty_text=describe(l), quantity=l.quantity,
                              rate_paise=l.rate_paise, amount_paise=l.quantity * l.rate_paise))
    return Bill(number=number, order_id=order.id, customer_name=order.customer_name, city=order.city,
                transport=order.transport, payment=order.payment, lines=lines,
                total_paise=sum(l.amount_paise for l in lines), created_at=created_at)


def packing_list(order: Order, catalog: Catalog) -> list[tuple[str, str, int]]:
    """(item name, size or '-', quantity): one row per size, in order."""
    rows = []
    for l in order.lines:
        item = catalog.get(l.item_code)
        name = item.name if item else l.item_code
        if l.sizes:
            rows.extend((name, size, qty) for size, qty in l.sizes.items())
        else:
            rows.append((name, "-", l.quantity))
    return rows


def share_text(bill: Bill) -> str:
    who = bill.customer_name + (f", {bill.city}" if bill.city else "")
    out = [f"{TITLE} No. {bill.number}", f"{who} · {bill.created_at}", ""]
    for i, l in enumerate(bill.lines, 1):
        out.append(f"{i}. {l.name} ({l.qty_text}) {l.quantity} × {format_inr(l.rate_paise)} = "
                   f"{format_inr(l.amount_paise)}")
    out += ["", f"Total {format_inr(bill.total_paise)}",
            f"Transport: {bill.transport or 'not set'} · Payment: {bill.payment or 'not set'}", FOOTER]
    return "\n".join(out)
