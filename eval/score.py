"""Scoring one eval conversation against its correct answer ("gold").

- order_correct: every saved order matches gold exactly (customer, lines, transport, payment), and when gold says the
  agent should have asked (e.g. no shop name), it asked a question and saved nothing invented.
- lines_right / lines_total: gold lines found exactly (item code and sizes, or item code and quantity).
- wrong_saved: saved lines that match no gold line. These passed the owner's read-back unnoticed in a real shop only
  if he missed it, so they are the costly kind of error ("silent errors").
- claims_caught: turns where the code had to correct the AI for claiming an action no tool performed.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass, field

from app.agent.say import T

NOT_DONE = set(T["not_done"].values())


@dataclass
class CaseRun:
    orders: list[dict]          # saved orders: {"customer", "lines": [{"item_code","sizes","quantity"}], ...}
    turns: list[dict] = field(default_factory=list)  # {"spoken": [...], "tool_calls": [...], "ms", "cost_paise"}
    bills: int = 0                                   # invoices issued (not voided)
    balances: dict[str, int] = field(default_factory=dict)  # customer -> khata balance in paise


@dataclass
class CaseScore:
    id: str
    order_correct: bool
    lines_right: int
    lines_total: int
    wrong_saved: int
    claims_caught: int
    turn_ms: list[int]
    cost_paise: int


def _line_ok(gold: dict, got: dict) -> bool:
    if gold["item_code"] != got.get("item_code"):
        return False
    if "rate" in gold and gold["rate"] * 100 != got.get("rate_paise"):
        return False
    if gold.get("sizes"):
        return gold["sizes"] == got.get("sizes")
    return not got.get("sizes") and gold.get("quantity") == got.get("quantity")


def _same(a: str | None, b: str | None) -> bool:
    return (a or "").strip().casefold() == (b or "").strip().casefold()


def score_case(case: dict, run: CaseRun) -> CaseScore:
    gold = case["gold"]
    gold_orders = gold.get("orders", [])
    right = wrong = 0
    total = sum(len(o["lines"]) for o in gold_orders)
    correct = len(run.orders) == len(gold_orders)
    for got in run.orders:
        want = next((g for g in gold_orders if _same(g["customer"], got["customer"])), None)
        want_lines = list(want["lines"]) if want else []
        for line in got["lines"]:
            match = next((g for g in want_lines if _line_ok(g, line)), None)
            if match:
                right += 1
                want_lines.remove(match)
            else:
                wrong += 1
        if want is None or want_lines or len(got["lines"]) != len(want["lines"]):
            correct = False
        elif any(k in want and not _same(want[k], got.get(k)) for k in ("transport", "payment")):
            correct = False
    if "bills" in gold and gold["bills"] != run.bills:
        correct = False
    if any(run.balances.get(name) != paise for name, paise in gold.get("balances", {}).items()):
        correct = False
    if gold.get("ask"):
        asked = any("?" in s for t in run.turns for s in t["spoken"])
        correct = correct and asked
    caught = sum(1 for t in run.turns if any(s in NOT_DONE for s in t["spoken"]))
    return CaseScore(id=case["id"], order_correct=correct, lines_right=right, lines_total=total, wrong_saved=wrong,
                     claims_caught=caught, turn_ms=[t["ms"] for t in run.turns],
                     cost_paise=sum(t["cost_paise"] for t in run.turns))


def summary(scores: list[CaseScore]) -> dict:
    total = sum(s.lines_total for s in scores)
    ms = [m for s in scores for m in s.turn_ms]
    return {"cases": len(scores), "orders_correct": sum(s.order_correct for s in scores),
            "line_accuracy": round(sum(s.lines_right for s in scores) / total, 3) if total else None,
            "wrong_saved_lines": sum(s.wrong_saved for s in scores),
            "claims_caught": sum(s.claims_caught for s in scores),
            "p50_ms": int(statistics.median(ms)) if ms else None,
            "p90_ms": int(statistics.quantiles(ms, n=10)[-1]) if len(ms) >= 2 else None,
            "cost_paise": sum(s.cost_paise for s in scores)}
