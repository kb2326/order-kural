"""The GST tax invoice, laid out like the shop's own hand-written invoice, and the packing list for staff.

Law (CGST Act s.31, Rule 46): a registered supplier issues a tax invoice for every taxable supply. Garments: 5% GST
up to Rs 2,500 per piece, 18% above (from 22 Sep 2025). Another state = IGST; same state = CGST + SGST halves.
All money is integer paise; tax is computed per line, half-up to the paisa; the grand total is rounded to the rupee."""
from __future__ import annotations

from dataclasses import dataclass

from app.domain.catalog import Catalog
from app.domain.money import format_inr
from app.domain.order import Order
from app.domain.gst import STATE_NAMES, state_code_for, valid_gstin  # noqa: F401 (re-exported)
from app.domain.rules import gst_pct

TITLE = "TAX INVOICE"
EWAY_THRESHOLD_PAISE = 50_000_00
def invoice_number(prefix: str, number: int, date: str) -> str:
    """One series per financial year (April-March), e.g. KG/26-27/0007."""
    year, month = int(date[:4]), int(date[5:7])
    start = year if month >= 4 else year - 1
    return f"{prefix}/{start % 100:02d}-{(start + 1) % 100:02d}/{number:04d}"


_ONES = ("Zero One Two Three Four Five Six Seven Eight Nine Ten Eleven Twelve Thirteen Fourteen Fifteen Sixteen "
         "Seventeen Eighteen Nineteen").split()
_TENS = "_ _ Twenty Thirty Forty Fifty Sixty Seventy Eighty Ninety".split()


def _below_100(n: int) -> str:
    return _ONES[n] if n < 20 else _TENS[n // 10] + (f" {_ONES[n % 10]}" if n % 10 else "")


def _below_1000(n: int) -> str:
    head = f"{_ONES[n // 100]} Hundred" if n >= 100 else ""
    tail = _below_100(n % 100) if n % 100 else ""
    return " ".join(p for p in (head, tail) if p)


def amount_in_words(rupees: int) -> str:
    """Indian system: 460138 -> 'Four Lakh Sixty Thousand One Hundred Thirty Eight Rupees Only'."""
    if rupees == 0:
        return "Zero Rupees Only"
    parts = []
    for size, name in ((10_000_000, "Crore"), (100_000, "Lakh"), (1000, "Thousand")):
        if rupees >= size:
            parts.append(f"{amount_in_words(rupees // size).removesuffix(' Rupees Only')} {name}")
            rupees %= size
    if rupees:
        parts.append(_below_1000(rupees))
    return " ".join(parts) + " Rupees Only"


@dataclass(frozen=True)
class InvoiceLine:
    sno: int
    item_code: str
    name: str
    hsn: str
    size: str
    qty: int
    rate_paise: int
    amount_paise: int
    gst_pct: int


@dataclass(frozen=True)
class Invoice:
    number: int
    invoice_no: str
    date: str
    order_id: int
    buyer_name: str
    buyer_city: str | None
    buyer_gstin: str | None
    place_of_supply: str
    interstate: bool
    b2b: bool
    transport: str | None
    payment: str | None
    lines: list[InvoiceLine]
    total_pcs: int
    taxable_paise: int
    cgst_paise: int
    sgst_paise: int
    igst_paise: int
    round_off_paise: int
    grand_total_paise: int
    amount_in_words: str
    gst_rates: list[int]
    eway_bill_needed: bool


def make_invoice(order: Order, catalog: Catalog, shop: dict, number: int, date: str) -> Invoice:
    gstin = order.gstin if order.gstin and valid_gstin(order.gstin) else None
    pos = order.state_code or state_code_for(gstin, order.city)
    if pos is None:
        raise ValueError(f"Say the state or GSTIN of {order.customer_name} for the invoice")
    interstate = pos != shop["state_code"]
    lines, cgst = [], 0
    sgst = igst = 0
    for i, l in enumerate(order.lines, 1):
        item = catalog.get(l.item_code)
        amount = l.quantity * l.rate_paise
        pct = gst_pct(l.rate_paise)
        if interstate:
            igst += (amount * pct + 50) // 100
        else:
            half = (amount * pct + 100) // 200
            cgst, sgst = cgst + half, sgst + half
        lines.append(InvoiceLine(sno=i, item_code=l.item_code, name=item.name if item else l.item_code,
                                 hsn=item.hsn if item else "", size=", ".join(l.sizes) if l.sizes else "",
                                 qty=l.quantity, rate_paise=l.rate_paise, amount_paise=amount, gst_pct=pct))
    taxable = sum(l.amount_paise for l in lines)
    exact = taxable + cgst + sgst + igst
    grand = (exact + 50) // 100 * 100
    return Invoice(number=number, invoice_no=invoice_number(shop["invoice_prefix"], number, date), date=date,
                   order_id=order.id, buyer_name=order.customer_name, buyer_city=order.city, buyer_gstin=gstin,
                   place_of_supply=pos, interstate=interstate, b2b=gstin is not None, transport=order.transport,
                   payment=order.payment, lines=lines, total_pcs=sum(l.qty for l in lines), taxable_paise=taxable,
                   cgst_paise=cgst, sgst_paise=sgst, igst_paise=igst, round_off_paise=grand - exact,
                   grand_total_paise=grand, amount_in_words=amount_in_words(grand // 100),
                   gst_rates=sorted({l.gst_pct for l in lines}),
                   eway_bill_needed=interstate and grand > EWAY_THRESHOLD_PAISE)


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


def tax_lines(inv: Invoice) -> list[tuple[str, int]]:
    rate = "/".join(str(r) for r in inv.gst_rates)
    if inv.interstate:
        return [(f"IGST {rate}%", inv.igst_paise)]
    half = "/".join(f"{r / 2:g}" for r in inv.gst_rates)
    return [(f"CGST {half}%", inv.cgst_paise), (f"SGST {half}%", inv.sgst_paise)]


def share_text(inv: Invoice, shop: dict) -> str:
    who = inv.buyer_name + (f", {inv.buyer_city}" if inv.buyer_city else "")
    out = [f"{TITLE} {inv.invoice_no}", f"{shop['name']} → {who} · {inv.date}",
           f"Buyer GSTIN: {inv.buyer_gstin or 'Unregistered (B2C)'} · Place of supply: "
           f"{STATE_NAMES.get(inv.place_of_supply, inv.place_of_supply)} ({inv.place_of_supply})", ""]
    for l in inv.lines:
        out.append(f"{l.sno}. {l.name} {l.size} · {l.qty} × {format_inr(l.rate_paise)} = {format_inr(l.amount_paise)}")
    out += ["", f"Total pcs {inv.total_pcs} · Taxable {format_inr(inv.taxable_paise)}"]
    out += [f"{name} {format_inr(paise)}" for name, paise in tax_lines(inv)]
    out += [f"Round off {format_inr(inv.round_off_paise)}", f"Grand total {format_inr(inv.grand_total_paise)}",
            inv.amount_in_words,
            f"Transport: {inv.transport or 'not set'} · Payment: {inv.payment or 'not set'}"]
    return "\n".join(out)
