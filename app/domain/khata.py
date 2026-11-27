"""The khata (credit ledger). Append-only: a bill adds to what the buyer owes, a payment subtracts, and a mistake is
fixed by a reversal entry, never by deleting. Positive balance = the buyer owes the shop."""
from __future__ import annotations

SIGN = {"bill": 1, "payment": -1}


def balance(entries: list[dict]) -> int:
    by_id = {e["id"]: e for e in entries}
    total = 0
    for e in entries:
        if e["kind"] == "reversal":
            target = by_id[e["reverses"]]
            total -= SIGN[target["kind"]] * target["amount_paise"]
        else:
            total += SIGN[e["kind"]] * e["amount_paise"]
    return total
