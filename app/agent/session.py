"""The agent's hands: the tools the LLM may call, over the shop's tested services.

Rules this file enforces, whatever the LLM does:
- Write tools only *stage* a change. Nothing is saved until confirm_pending runs AND the owner's last words were a yes
  word (words.classify), or he tapped Sari.
- One thing waits for "sari" at a time. More changes for the same customer merge into it; anything else is refused
  until he says sari or cancel.
- Every sentence about orders, bills, khata or answers comes from say.render, from facts these tools computed.
"""
from __future__ import annotations

import difflib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.agent import say, words
from app.domain.catalog import normalise
from app.domain.changes import CustomerRef, PieceResult
from app.domain.order import Order, describe
from app.domain.rules import normalise_payment
from app.flow import ask
from app.flow.pieces import PieceService, Proposal
from app.flow.shop import ShopError, ShopService

TOOL_NAMES = ("find_customer", "get_open_order", "add_to_order", "change_line", "remove_line", "set_detail",
              "bill_order", "record_payment", "mark_shipped", "ask_shop", "confirm_pending", "discard_pending")


@dataclass
class ToolResult:
    facts: dict
    say: str
    ui: dict
    wrote: bool


@dataclass
class Pending:
    kind: str  # "order" | "bill" | "payment" | "ship"
    customer: str
    piece_id: int | None = None
    changes: list[dict] = field(default_factory=list)
    city: str | None = None
    args: dict = field(default_factory=dict)
    view: dict = field(default_factory=dict)


def _total(order: Order) -> int:
    return sum(l.quantity * l.rate_paise for l in order.lines)


class AgentSession:
    def __init__(self, pieces: PieceService, shop: ShopService, source: str = "live", now=None):
        self.pieces = pieces
        self.shop = shop
        self.store = pieces.store
        self.catalog = pieces.catalog
        self.source = source
        self.now = now or (lambda: datetime.now(timezone.utc))
        self.pending: Pending | None = None
        self.language = say.DEFAULT
        self.last_user_text = ""

    # ---- plumbing ------------------------------------------------------------------------------------------
    def heard(self, text: str, language: str | None = None) -> None:
        """Called by every brain before each LLM turn, with what the owner just said."""
        self.last_user_text = text
        if language:
            self.language = say.lang(language)

    def _say(self, kind: str, facts: dict, wrote: bool) -> ToolResult:
        return ToolResult(facts=facts, say=say.render(kind, facts, self.language), ui=self.slip(), wrote=wrote)

    def _quiet(self, facts: dict) -> ToolResult:
        """A read tool: facts go back to the LLM, nothing is spoken by code."""
        return ToolResult(facts=facts, say="", ui=self.slip(), wrote=False)

    def slip(self) -> dict:
        p = self.pending
        return {"pending": None if p is None else {"kind": p.kind, "customer": p.customer, **p.view}}

    def _name(self, code: str) -> str:
        item = self.catalog.get(code)
        return item.name if item else code

    def _lines_view(self, order: Order) -> list[dict]:
        return [{"item": self._name(l.item_code), "qty": describe(l), "rate_paise": l.rate_paise,
                 "amount_paise": l.quantity * l.rate_paise, "flags": l.flags} for l in order.lines]

    def _open_order(self, customer: str) -> Order | None:
        wanted = normalise(customer)
        found = [o for o in self.store.open_orders() if normalise(o.customer_name) == wanted]
        return found[-1] if found else None

    def _customer_id(self, customer: str) -> int | None:
        found = self.store.find_customers(customer)
        return found[0]["id"] if found else None

    def _near_customer(self, customer: str) -> str | None:
        names = [c["name"] for c in self.store.all_customers()]
        close = difflib.get_close_matches(customer, names, n=1, cutoff=0.75)
        return close[0] if close else None

    def _busy(self, customer: str, kind: str) -> ToolResult | None:
        p = self.pending
        if p and (p.kind != kind or kind != "order" or normalise(p.customer) != normalise(customer)):
            return self._say("other_pending", {"customer": p.customer}, wrote=False)
        return None

    # ---- read tools ----------------------------------------------------------------------------------------
    def find_customer(self, name: str, city: str | None = None) -> ToolResult:
        matches = [c for c in self.store.find_customers(name) if not city or not c["city"]
                   or normalise(c["city"]) == normalise(city)]
        return self._quiet({"matches": matches, "near": self._near_customer(name) if not matches else None})

    def get_open_order(self, customer: str) -> ToolResult:
        order = self._open_order(customer)
        if order is None:
            return self._quiet({"customer": customer, "open_order": None})
        return self._quiet({"customer": order.customer_name, "lines": self._lines_view(order),
                            "transport": order.transport, "payment": order.payment, "total_paise": _total(order)})

    # ---- order changes -------------------------------------------------------------------------------------
    def add_to_order(self, customer: str, items: list[dict], city: str | None = None) -> ToolResult:
        changes = [{"op": "add_line", "name_as_spoken": i.get("name_as_spoken") or i.get("item_code") or "",
                    "item_code": i.get("item_code") or None, "sizes": i.get("sizes") or {},
                    "quantity_total": i.get("quantity_total"), "rate_spoken": i.get("rate_spoken")} for i in items]
        return self._stage_order(customer, city, changes)

    def change_line(self, customer: str, item_code: str, sizes: dict | None = None,
                    quantity_total: int | None = None) -> ToolResult:
        return self._stage_order(customer, None, [{"op": "change_line", "item_code": item_code, "sizes": sizes,
                                                   "quantity_total": quantity_total}])

    def remove_line(self, customer: str, item_code: str) -> ToolResult:
        return self._stage_order(customer, None, [{"op": "remove_line", "item_code": item_code}])

    def set_detail(self, customer: str, field: str, value: str) -> ToolResult:
        return self._stage_order(customer, None, [{"op": "set_field", "field": field, "value": value}])

    def _stage_order(self, customer: str, city: str | None, changes: list[dict]) -> ToolResult:
        customer = (customer or "").strip()
        if not customer:
            return self._say("ask_customer", {"near": None}, wrote=False)
        busy = self._busy(customer, "order")
        if busy:
            return busy
        old = self.pending
        combined = (old.changes if old else []) + changes
        city = city or (old.city if old else None)
        result = PieceResult(intent="order_changes", changes=combined,
                             customer=CustomerRef(name_as_spoken=customer, city=city))
        proposal: Proposal = self.pieces.propose(self.last_user_text, result, source=self.source)
        if proposal.ask_customer:
            near = self._near_customer(customer) if proposal.readback.startswith("Is this for") else None
            return self._say("ask_customer", {"near": near}, wrote=False)
        if not proposal.diff:
            return self._say("problems", {"customer": customer, "problems": proposal.problems}, wrote=False)
        if old and old.piece_id:
            self.pieces.discard(old.piece_id)
        changed = [f"{self._name(d.item_code)} {d.after}" if d.item_code else f"{d.field} {d.after}"
                   for d in proposal.diff if d.after]
        removed = [f"{self._name(d.item_code)} removed" for d in proposal.diff if d.kind == "removed"]
        total = _total(proposal.order)
        self.pending = Pending(kind="order", customer=proposal.order.customer_name, piece_id=proposal.piece_id,
                               changes=combined, city=city,
                               view={"lines": self._lines_view(proposal.order), "total_paise": total,
                                     "transport": proposal.order.transport, "payment": proposal.order.payment,
                                     "problems": proposal.problems, "is_new_order": proposal.is_new_order})
        return self._say("staged", {"customer": proposal.order.customer_name, "changes": changed + removed,
                                    "total_paise": total, "problems": proposal.problems,
                                    "piece_id": proposal.piece_id}, wrote=True)

    # ---- bill, payment, shipping ---------------------------------------------------------------------------
    def bill_order(self, customer: str) -> ToolResult:
        busy = self._busy(customer, "bill")
        if busy:
            return busy
        order = self._open_order(customer)
        if order is None or not order.lines:
            return self._say("no_open_order", {"customer": customer}, wrote=False)
        total = _total(order)
        self.pending = Pending(kind="bill", customer=order.customer_name, args={"order_id": order.id},
                               view={"lines": self._lines_view(order), "total_paise": total})
        return self._say("bill_staged", {"customer": order.customer_name, "total_paise": total}, wrote=True)

    def record_payment(self, customer: str, amount_rupees: int, mode: str) -> ToolResult:
        busy = self._busy(customer, "payment")
        if busy:
            return busy
        customer_id = self._customer_id(customer)
        if customer_id is None:
            return self._say("ask_customer", {"near": self._near_customer(customer)}, wrote=False)
        if not amount_rupees or amount_rupees <= 0:
            return self._say("problems", {"customer": customer, "problems": ["Amount not clear"]}, wrote=False)
        mode = normalise_payment(mode or "") or "cash"
        name = self.store.customer_name(customer_id)
        self.pending = Pending(kind="payment", customer=name,
                               args={"customer_id": customer_id, "amount_paise": amount_rupees * 100, "mode": mode},
                               view={"amount_paise": amount_rupees * 100, "mode": mode})
        return self._say("payment_staged", {"customer": name, "amount_paise": amount_rupees * 100, "mode": mode},
                         wrote=True)

    def mark_shipped(self, customer: str, transport: str | None = None) -> ToolResult:
        busy = self._busy(customer, "ship")
        if busy:
            return busy
        wanted = normalise(customer)
        found = [o for o in self.store.orders_in_states(["open", "billed"]) if normalise(o.customer_name) == wanted]
        if not found:
            return self._say("no_open_order", {"customer": customer}, wrote=False)
        order = found[-1]
        self.pending = Pending(kind="ship", customer=order.customer_name,
                               args={"order_id": order.id, "transport": transport}, view={"transport": transport})
        return self._say("shipped_staged", {"customer": order.customer_name, "transport": transport}, wrote=True)

    # ---- ask the shop --------------------------------------------------------------------------------------
    def ask_shop(self, question: str, customer: str | None = None, item: str | None = None) -> ToolResult:
        if question == "to_ship":
            answer = ask.to_ship(self.store, self.catalog)
        elif question == "customer" and customer:
            customer_id = self._customer_id(customer)
            if customer_id is None:
                return self._say("ask_customer", {"near": self._near_customer(customer)}, wrote=False)
            answer = ask.customer_summary(self.store, self.catalog, customer_id)
        elif question == "item_count" and item:
            found = self.catalog.get(item) or self.catalog.match(item)
            if found is None:
                return self._say("cannot_answer", {}, wrote=False)
            answer = ask.item_count(self.store, self.catalog, found.code, now=self.now())
        else:
            return self._say("cannot_answer", {}, wrote=False)
        return self._say(answer.kind, answer.facts, wrote=False)

    # ---- approval ------------------------------------------------------------------------------------------
    def confirm_pending(self) -> ToolResult:
        p = self.pending
        if p is None:
            return self._say("nothing_pending", {}, wrote=False)
        if words.classify(self.last_user_text) != "yes":
            return self._say("need_yes", {"customer": p.customer}, wrote=False)
        try:
            result = self._apply(p)
        except ShopError as e:
            self.pending = None
            return self._say("problems", {"customer": p.customer, "problems": [str(e)]}, wrote=False)
        self.pending = None
        return result

    def _apply(self, p: Pending) -> ToolResult:
        if p.kind == "order":
            order = self.pieces.confirm(p.piece_id)
            return self._say("saved", {"customer": order.customer_name, "total_paise": _total(order),
                                       "order_id": order.id}, wrote=True)
        if p.kind == "bill":
            bill = self.shop.issue_bill(p.args["order_id"])
            return self._say("bill_saved", {"number": bill.number, "total_paise": bill.total_paise}, wrote=True)
        if p.kind == "payment":
            new_balance = self.shop.record_payment(p.args["customer_id"], p.args["amount_paise"], p.args["mode"])
            return self._say("payment_saved", {"customer": p.customer, "balance_paise": new_balance}, wrote=True)
        self.shop.mark_shipped(p.args["order_id"], p.args["transport"])
        return self._say("shipped_saved", {"customer": p.customer}, wrote=True)

    def discard_pending(self) -> ToolResult:
        p = self.pending
        if p is None:
            return self._say("nothing_pending", {}, wrote=False)
        if p.kind == "order" and p.piece_id:
            self.pieces.discard(p.piece_id)
        self.pending = None
        return self._say("discarded", {}, wrote=True)

    def call(self, name: str, args: dict[str, Any]) -> ToolResult:
        """Run a tool by name with LLM-supplied arguments; unknown names or bad arguments never crash a turn."""
        if name not in TOOL_NAMES:
            return self._quiet({"error": f"Unknown tool {name}"})
        try:
            return getattr(self, name)(**args)
        except TypeError as e:
            return self._quiet({"error": f"Bad arguments for {name}: {e}"})
