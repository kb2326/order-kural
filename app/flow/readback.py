"""What the app says back before anything is saved. English for now; Tamil voice comes in slice S4."""
from __future__ import annotations

from app.domain.catalog import Catalog
from app.domain.money import format_inr
from app.domain.order import DiffEntry, Order
from app.domain.rules import Totals


def _rate(paise: int) -> str:
    return f"₹{paise // 100}" if paise % 100 == 0 else format_inr(paise)


def build_readback(order: Order, diff: list[DiffEntry], totals: Totals, missing: list[str],
                   catalog: Catalog, problems: list[str] | None = None) -> str:
    who = order.customer_name + (f", {order.city}" if order.city else "")
    parts = [f"{who}."]
    lines = {l.item_code: l for l in order.lines}
    for d in diff:
        item = catalog.get(d.item_code) if d.item_code else None
        name = item.name if item else (d.item_code or "")
        if d.kind == "added":
            parts.append(f"Added: {name} {d.after} at {_rate(lines[d.item_code].rate_paise)}.")
        elif d.kind == "changed":
            parts.append(f"Changed: {name} {d.before} to {d.after}.")
        elif d.kind == "removed":
            parts.append(f"Removed: {name}.")
        elif d.kind == "set":
            parts.append(f"{(d.field or '').capitalize()}: {d.after}.")
    for p in problems or []:
        parts.append(f"Problem: {p}.")
    parts.append(f"Order total {format_inr(totals.total_paise)} with GST.")
    if missing:
        parts.append(f"Still needed: {', '.join(missing)}.")
    parts.append("Say sari to confirm.")
    return " ".join(parts)
