"""The printable order bill and packing list at /bill/{number}. Plain HTML, every value escaped."""
from __future__ import annotations

from html import escape

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from app.domain.bill import FOOTER, TITLE
from app.flow.shop import ShopService

pages = APIRouter()

CSS = """
body{font-family:"Noto Sans",system-ui,sans-serif;color:#1b1b1b;background:#fff;max-width:720px;margin:0 auto;
     padding:16px}
h1{font-size:1.3rem;margin:0 0 4px}.sub{color:#555;margin:0 0 14px}
table{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums;margin:8px 0}
th,td{border-bottom:1px solid #ddd;padding:6px 4px;text-align:left;vertical-align:top}
.n{text-align:right;white-space:nowrap}.total td{font-weight:700;font-size:1.1rem;border-bottom:0}
.foot{color:#555;font-size:.9rem}.void{color:#b3261e;font-weight:700}
h2{font-size:1.05rem;margin:28px 0 4px;page-break-before:always}
@media print{.noprint{display:none}}
"""


@pages.get("/bill/{number}", response_class=HTMLResponse, include_in_schema=False)
def bill_page(number: int, request: Request) -> str:
    live = request.app.state.pieces
    b = ShopService(live.store, live.catalog).bill_view(number)
    if b is None:
        raise HTTPException(status_code=404, detail="Bill not found")
    e = lambda v: escape(str(v if v is not None else ""))  # noqa: E731
    rows = "".join(f"<tr><td>{i}</td><td>{e(l['name'])}<br><small>{e(l['qty_text'])} · HSN {e(l['hsn'])}</small></td>"
                   f"<td class=n>{l['quantity']}</td><td class=n>{e(l['rate'])}</td><td class=n>{e(l['amount'])}</td>"
                   f"</tr>" for i, l in enumerate(b["lines"], 1))
    packing = "".join(f"<tr><td>{e(p['item'])}</td><td>{e(p['size'])}</td><td class=n>{p['qty']}</td>"
                      f"<td>☐</td></tr>" for p in b["packing"])
    who = e(b["customer"]) + (f", {e(b['city'])}" if b["city"] else "")
    void = "<p class=void>This bill was undone (voided).</p>" if b["voided"] else ""
    return f"""<!doctype html><html lang=en><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1"><title>Bill {number} · Order Kural</title>
<style>{CSS}</style></head><body>
<p class=noprint><a href="/">← Back</a> · <button onclick="print()">Print</button></p>
<h1>{TITLE} No. {number}</h1><p class=sub>{who} · {e(b['date'])}</p>{void}
<table><thead><tr><th>#</th><th>Item</th><th class=n>Qty</th><th class=n>Rate</th><th class=n>Amount</th></tr></thead>
<tbody>{rows}<tr class=total><td></td><td>Total</td><td></td><td></td><td class=n>{e(b['total'])}</td></tr></tbody>
</table>
<p>Transport: {e(b['transport'] or 'not set')} · Payment: {e(b['payment'] or 'not set')}</p>
<p class=foot>{FOOTER}</p>
<h2>Packing list · Bill {number} · {who}</h2>
<table><thead><tr><th>Item</th><th>Size</th><th class=n>Qty</th><th>Packed</th></tr></thead><tbody>{packing}</tbody>
</table></body></html>"""
