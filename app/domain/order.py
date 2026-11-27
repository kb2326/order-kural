"""The order engine: apply one piece's change list to an order. Pure: returns a new order, never mutates."""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Literal

from app.domain.catalog import Catalog
from app.domain.changes import AddLine, Change, ChangeLine, RemoveLine, SetField
from app.domain.rules import Payment, line_flags, normalise_payment


@dataclass
class OrderLine:
    item_code: str
    sizes: dict[str, int]
    quantity: int
    rate_paise: int
    flags: list[str] = field(default_factory=list)
    source_piece_id: int | None = None


@dataclass
class Order:
    id: int | None
    customer_name: str
    city: str | None
    state: Literal["open", "billed", "shipped", "cancelled"]
    transport: str | None
    payment: Payment | None
    lines: list[OrderLine]


@dataclass
class DiffEntry:
    kind: Literal["added", "changed", "removed", "set"]
    item_code: str | None
    field: str | None
    before: str | None
    after: str | None


@dataclass
class ApplyResult:
    order: Order
    diff: list[DiffEntry]
    problems: list[str]


def describe(line: OrderLine) -> str:
    """'S 6, M 6, L 6' when sized, else the plain quantity '24'."""
    if line.sizes:
        return ", ".join(f"{size} {qty}" for size, qty in line.sizes.items())
    return str(line.quantity)


def _find(order: Order, code: str) -> OrderLine | None:
    return next((l for l in order.lines if l.item_code == code), None)


def _add(new: Order, ch: AddLine, catalog: Catalog, diff: list[DiffEntry], problems: list[str]) -> None:
    item = catalog.get(ch.item_code) if ch.item_code else None
    if item is not None and not catalog.plausible(item, ch.name_as_spoken):
        problems.append(f"Item code {item.code} does not match '{ch.name_as_spoken}'")
        return
    item = item or catalog.match(ch.name_as_spoken)
    if item is None:
        close = catalog.closest(ch.name_as_spoken)
        hint = f". Closest: {', '.join(i.name for i in close)}" if close else ""
        problems.append(f"Unknown item: {ch.name_as_spoken}{hint}")
        return
    sizes = {s: q for s, q in ch.sizes.items() if q > 0}
    added = sum(sizes.values()) if sizes else (ch.quantity_total or 0)
    if added == 0:
        problems.append(f"No quantity for: {ch.name_as_spoken}")
        return
    existing = _find(new, item.code)
    if existing is not None and bool(existing.sizes) != bool(sizes):
        problems.append(f"Sizes needed for: {item.name}" if existing.sizes else f"Sizes don't match for: {item.name}")
        return
    if existing is None:
        rate = ch.rate_spoken * 100 if ch.rate_spoken else item.rate_paise
        line = OrderLine(item_code=item.code, sizes=sizes, quantity=added, rate_paise=rate)
        new.lines.append(line)
        diff.append(DiffEntry("added", item.code, None, None, describe(line)))
        return
    before = describe(existing)
    for s, q in sizes.items():
        existing.sizes[s] = existing.sizes.get(s, 0) + q
    existing.quantity += added
    if ch.rate_spoken:
        existing.rate_paise = ch.rate_spoken * 100
    diff.append(DiffEntry("changed", item.code, None, before, describe(existing)))


def _change(new: Order, ch: ChangeLine, catalog: Catalog, diff: list[DiffEntry], problems: list[str]) -> None:
    existing = _find(new, ch.item_code)
    if existing is None:
        problems.append(f"Not in order: {ch.item_code}")
        return
    before = describe(existing)
    if ch.sizes is not None:
        for s, q in ch.sizes.items():
            if q == 0:
                existing.sizes.pop(s, None)
            else:
                existing.sizes[s] = q
        existing.quantity = sum(existing.sizes.values())
    elif ch.quantity_total is not None:
        if existing.sizes:
            item = catalog.get(existing.item_code)
            problems.append(f"Sizes needed for: {item.name if item else existing.item_code}")
            return
        existing.quantity = ch.quantity_total
    if ch.rate_spoken:
        existing.rate_paise = ch.rate_spoken * 100
    if existing.quantity == 0:
        new.lines.remove(existing)
        diff.append(DiffEntry("removed", ch.item_code, None, before, None))
    else:
        diff.append(DiffEntry("changed", ch.item_code, None, before, describe(existing)))


def apply_changes(order: Order, changes: list[Change], catalog: Catalog) -> ApplyResult:
    new = copy.deepcopy(order)
    diff: list[DiffEntry] = []
    problems: list[str] = []

    for ch in changes:
        if isinstance(ch, AddLine):
            _add(new, ch, catalog, diff, problems)
        elif isinstance(ch, ChangeLine):
            _change(new, ch, catalog, diff, problems)
        elif isinstance(ch, RemoveLine):
            existing = _find(new, ch.item_code)
            if existing is None:
                problems.append(f"Not in order: {ch.item_code}")
                continue
            new.lines.remove(existing)
            diff.append(DiffEntry("removed", ch.item_code, None, describe(existing), None))
        elif isinstance(ch, SetField):
            if ch.field == "payment":
                value = normalise_payment(ch.value)
                if value is None:
                    problems.append(f"Unclear payment: {ch.value}")
                    continue
            else:
                value = ch.value.strip()
            before = getattr(new, ch.field)
            setattr(new, ch.field, value)
            diff.append(DiffEntry("set", None, ch.field, before, value))

    for line in new.lines:
        item = catalog.get(line.item_code)
        line.flags = line_flags(line, item) if item else []
    return ApplyResult(order=new, diff=diff, problems=problems)
