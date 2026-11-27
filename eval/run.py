"""Run the eval: every case on a fresh, empty shop, through the real text brain (Sarvam chat with tools).

Usage:  python -m eval.run            (needs SARVAM_API_KEY; costs a few paise per turn)
Writes eval/reports/<date>-sarvam.md and .json. Commit the report whatever it shows.
"""
from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import asdict
from datetime import date
from pathlib import Path

from app.agent.session import AgentSession
from app.agent.text_loop import TextBrain
from app.domain.catalog import Catalog
from app.flow.pieces import PieceService
from app.flow.shop import ShopService
from app.store.db import Store
from eval.score import CaseRun, score_case, summary

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "eval" / "cases.json"
REPORTS = ROOT / "eval" / "reports"


def run_case(case: dict, key: str, catalog: Catalog) -> CaseRun:
    store = Store(":memory:")
    shop = ShopService(store, catalog)
    brain = TextBrain(AgentSession(PieceService(store, catalog), shop), key)
    turns = []
    for text in case["turns"]:
        start = time.perf_counter()
        r = brain.turn(text, case["language"])
        turns.append({"said": text, "spoken": r.spoken, "tool_calls": [c["name"] for c in r.tool_calls],
                      "ms": int((time.perf_counter() - start) * 1000), "cost_paise": r.cost_paise})
    orders = [{"customer": o.customer_name, "transport": o.transport, "payment": o.payment,
               "lines": [{"item_code": l.item_code, "sizes": l.sizes, "quantity": l.quantity,
                          "rate_paise": l.rate_paise} for l in o.lines]}
              for o in store.orders_in_states(["open", "billed", "shipped"])]
    balances = {c["name"]: shop.balance(c["id"]) for c in store.all_customers()}
    bills = sum(1 for b in store.all_bills() if not b["voided"])
    return CaseRun(orders=orders, turns=turns, bills=bills, balances=balances)


def main() -> None:
    key = os.environ.get("SARVAM_API_KEY", "").strip()
    if not key:
        sys.exit("Set SARVAM_API_KEY to run the eval.")
    catalog = Catalog.load(ROOT / "data" / "items.json")
    cases = json.loads(CASES.read_text(encoding="utf-8"))["cases"]
    scores, runs = [], {}
    for case in cases:
        run = run_case(case, key, catalog)
        s = score_case(case, run)
        scores.append(s)
        runs[case["id"]] = asdict(run)
        print(f"{'PASS' if s.order_correct else 'FAIL'}  {case['id']}  lines {s.lines_right}/{s.lines_total}  "
              f"wrong saved {s.wrong_saved}  claims caught {s.claims_caught}", flush=True)
    total = summary(scores)
    REPORTS.mkdir(parents=True, exist_ok=True)
    stem = REPORTS / f"{date.today().isoformat()}-sarvam"
    stem.with_suffix(".json").write_text(json.dumps({"summary": total, "scores": [asdict(s) for s in scores],
                                                     "runs": runs}, ensure_ascii=False, indent=1), encoding="utf-8")
    rows = "\n".join(f"| {s.id} | {next(c['source'] for c in cases if c['id'] == s.id)} | "
                     f"{'✅' if s.order_correct else '❌'} | {s.lines_right}/{s.lines_total} | {s.wrong_saved} | "
                     f"{s.claims_caught} |" for s in scores)
    stem.with_suffix(".md").write_text(
        f"# Eval report {date.today().isoformat()} (text brain, Sarvam sarvam-105b)\n\n"
        f"Orders fully correct: **{total['orders_correct']}/{total['cases']}** · line accuracy "
        f"**{total['line_accuracy']}** · wrong lines saved **{total['wrong_saved_lines']}** · claims caught by code "
        f"**{total['claims_caught']}** · p50 turn **{total['p50_ms']} ms** (p90 {total['p90_ms']} ms) · cost "
        f"**₹{total['cost_paise'] / 100:.2f}** estimated\n\n"
        f"| Case | Source | Correct | Lines | Wrong saved | Claims caught |\n|---|---|---|---|---|---|\n{rows}\n",
        encoding="utf-8")
    print(json.dumps(total))


if __name__ == "__main__":
    main()
