"""The voice-piece state machine: transcribed -> read_back -> applied | discarded.

propose() works out what a piece would change and reads it back, but saves nothing to the order.
confirm() is the only path that changes an order ("sari"). It re-applies the piece's change list to the order as it
is now, so two pieces read back at the same time cannot overwrite each other.
"""
from __future__ import annotations

import difflib
import json
from dataclasses import asdict, dataclass

from app.domain.catalog import Catalog, normalise
from app.domain.changes import CustomerRef, PieceResult
from app.domain.order import DiffEntry, Order, apply_changes
from app.domain.rules import Totals, compute_totals, missing_fields
from app.flow.readback import build_readback
from app.store.db import Store


class PieceStateError(Exception):
    """Confirm or discard called on a piece that is not waiting for confirmation."""


@dataclass
class Proposal:
    piece_id: int
    order_id: int | None
    is_new_order: bool
    order: Order
    diff: list[DiffEntry]
    totals: Totals
    missing: list[str]
    problems: list[str]
    readback: str
    ask_customer: bool


def candidates(ref: CustomerRef, open_orders: list[Order]) -> list[Order]:
    """Open orders this piece could belong to: the id the AI named, else same name in a compatible city."""
    by_id = [o for o in open_orders if ref.order_id is not None and o.id == ref.order_id]
    if by_id:
        return by_id
    if not ref.name_as_spoken:
        return []
    wanted, city = normalise(ref.name_as_spoken), normalise(ref.city or "")
    return [o for o in open_orders
            if normalise(o.customer_name) == wanted
            and (not city or not o.city or normalise(o.city) == city)]


def near_matches(ref: CustomerRef, open_orders: list[Order]) -> list[Order]:
    """Open orders whose customer name is close to, but not the same as, what was said ("Kerala Fancies")."""
    if not ref.name_as_spoken:
        return []
    wanted = normalise(ref.name_as_spoken)
    return [o for o in open_orders
            if normalise(o.customer_name) != wanted
            and difflib.SequenceMatcher(None, normalise(o.customer_name), wanted).ratio() >= 0.75]


def resolve_target(ref: CustomerRef, open_orders: list[Order]) -> Order | None:
    """Which open order does this piece belong to? None means start a new order (or ask, if several match)."""
    found = candidates(ref, open_orders)
    return found[0] if len(found) == 1 else None


def _new_order(ref: CustomerRef) -> Order:
    return Order(id=None, customer_name=(ref.name_as_spoken or "?").strip(), city=ref.city, state="open",
                 transport=None, payment=None, lines=[])


class PieceService:
    def __init__(self, store: Store, catalog: Catalog):
        self.store = store
        self.catalog = catalog

    def propose(self, transcript: str, result: PieceResult, source: str, audio_path: str | None = None) -> Proposal:
        piece_id = self.store.add_piece(transcript, source, audio_path)
        problems: list[str] = []
        ref = result.customer
        if result.intent != "order_changes":
            problems.append(f"Not supported yet: {result.intent}")
        if ref is None:
            problems.append("Customer not heard")
        open_orders = self.store.open_orders()
        found = candidates(ref, open_orders) if ref else []
        near = near_matches(ref, open_orders) if ref and not found else []
        ask_customer = ref is None or not ref.said or ref.confidence == "low" or len(found) > 1 or bool(near)

        target = found[0] if len(found) == 1 else None
        base = target or (_new_order(ref) if ref else _new_order(CustomerRef(name_as_spoken="?")))
        applied = apply_changes(base, result.changes if not problems else [], self.catalog)
        problems += applied.problems
        totals = compute_totals(applied.order, self.catalog)
        missing = missing_fields(applied.order)
        question = (f"Is this for {' or '.join(o.customer_name for o in near)}, or a new customer?" if near
                    else "Which customer is this for?")
        readback = (question if ask_customer else
                    build_readback(applied.order, applied.diff, totals, missing, self.catalog, problems))
        # Only a piece that was understood, names one customer and changes something can be confirmed.
        confirmable = not ask_customer and result.intent == "order_changes" and bool(applied.diff)

        self.store.update_piece(
            piece_id,
            state="read_back" if confirmable else "proposed",
            ai_result_json=result.model_dump_json(),
            proposal_json=json.dumps({"diff": [asdict(d) for d in applied.diff], "problems": problems}),
            target_order_id=target.id if target else None,
        )
        return Proposal(piece_id=piece_id, order_id=target.id if target else None, is_new_order=target is None,
                        order=applied.order, diff=applied.diff, totals=totals, missing=missing, problems=problems,
                        readback=readback, ask_customer=ask_customer)

    def _waiting(self, piece_id: int) -> dict:
        piece = self.store.get_piece(piece_id)
        if piece is None or piece["state"] != "read_back":
            state = piece["state"] if piece else "missing"
            raise PieceStateError(f"Piece {piece_id} is {state}, not waiting for confirmation")
        return piece

    def confirm(self, piece_id: int) -> Order:
        # One transaction under the store lock: a double tap or a crash half-way can never apply a piece twice.
        with self.store.tx():
            piece = self._waiting(piece_id)
            if not self.store.claim_piece(piece_id, "read_back", "applied"):
                raise PieceStateError(f"Piece {piece_id} was already handled")
            result = PieceResult.model_validate_json(piece["ai_result_json"])
            target = self.store.get_order(piece["target_order_id"]) if piece["target_order_id"] else None
            if target is None or target.state != "open":
                target = resolve_target(result.customer, self.store.open_orders()) or _new_order(result.customer)
            applied = apply_changes(target, result.changes, self.catalog)
            touched = {d.item_code for d in applied.diff if d.kind in ("added", "changed")}
            for line in applied.order.lines:
                if line.item_code in touched:
                    line.source_piece_id = piece_id
            order_id = self.store.save_order(applied.order)
            self.store.add_event(order_id, piece_id, json.dumps([asdict(d) for d in applied.diff]))
            self.store.update_piece(piece_id, order_id=order_id)
            return self.store.get_order(order_id)

    def discard_if_waiting(self, piece_id: int) -> None:
        """Drop a piece that will never be confirmed (it may never have reached read_back)."""
        self.store.claim_piece(piece_id, "read_back", "discarded")

    def discard(self, piece_id: int) -> None:
        with self.store.tx():
            self._waiting(piece_id)
            if not self.store.claim_piece(piece_id, "read_back", "discarded"):
                raise PieceStateError(f"Piece {piece_id} was already handled")
