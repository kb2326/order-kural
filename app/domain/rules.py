"""Business rules done by code, never by the AI: minimums, rate checks, GST and totals. All money in paise."""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from app.domain.catalog import Catalog, Item
    from app.domain.order import Order, OrderLine

GST_THRESHOLD_PAISE = 250000   # Rs 2,500 per piece
RATE_TOLERANCE_PCT = 10

Payment = Literal["cash", "upi", "credit", "bank"]
_PAYMENT_WORDS: dict[str, Payment] = {
    "credit": "credit", "kadan": "credit", "kadanu": "credit", "udhaar": "credit", "udhar": "credit",
    "cash": "cash", "rokkam": "cash",
    "upi": "upi", "gpay": "upi", "google pay": "upi", "phonepe": "upi", "paytm": "upi",
    "bank": "bank", "account": "bank", "account transfer": "bank", "neft": "bank", "rtgs": "bank",
    "advance": "bank",
}


def normalise_payment(value: str) -> Payment | None:
    key = " ".join(value.casefold().split())
    if key in _PAYMENT_WORDS:
        return _PAYMENT_WORDS[key]
    for word in key.split():
        if word in _PAYMENT_WORDS:
            return _PAYMENT_WORDS[word]
    return None


def line_flags(line: OrderLine, item: Item) -> list[str]:
    flags: list[str] = []
    if item.min_kind == "per_size":
        if not line.sizes:
            flags.append("sizes_missing")
        elif any(q < item.min_qty for q in line.sizes.values()):
            flags.append("below_min")
    elif item.min_kind == "total" and line.quantity < item.min_qty:
        flags.append("below_min")
    if abs(line.rate_paise - item.rate_paise) * 100 > item.rate_paise * RATE_TOLERANCE_PCT:
        flags.append("rate_off_list")
    return flags


def gst_pct(rate_paise: int) -> int:
    return 5 if rate_paise <= GST_THRESHOLD_PAISE else 18


@dataclass
class Totals:
    subtotal_paise: int
    gst_paise: int
    total_paise: int
    line_totals: dict[str, int]


def compute_totals(order: Order, catalog: Catalog) -> Totals:
    line_totals: dict[str, int] = {}
    gst = 0
    for line in order.lines:
        amount = line.quantity * line.rate_paise
        line_totals[line.item_code] = amount
        gst += (amount * gst_pct(line.rate_paise) + 50) // 100   # round half up to the paisa
    subtotal = sum(line_totals.values())
    return Totals(subtotal_paise=subtotal, gst_paise=gst, total_paise=subtotal + gst, line_totals=line_totals)


def missing_fields(order: Order) -> list[str]:
    missing = []
    if not order.customer_name:
        missing.append("customer")
    if not order.lines:
        missing.append("lines")
    if not order.transport:
        missing.append("transport")
    if not order.payment:
        missing.append("payment")
    return missing
