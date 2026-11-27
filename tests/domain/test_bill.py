"""The GST tax invoice (owner approved 27 Nov: 'bill it' makes a real tax invoice, in the shop's own layout)."""
import pytest

from app.domain.bill import amount_in_words, invoice_number, make_invoice, packing_list, share_text, state_code_for
from app.domain.catalog import Catalog
from app.domain.order import Order, OrderLine

CAT = Catalog.load("data/items.json")
SHOP = {"gstin": "33AAAAA0000A1Z5", "state_code": "33", "invoice_prefix": "KG"}


def order(city="Palakkad", gstin=None, state_code=None):
    return Order(id=5, customer_name="Kerala Fancy", city=city, state="open", transport="KPN", payment="credit",
                 lines=[OrderLine("PPL", {"S": 6, "M": 6, "L": 6, "XL": 6}, 24, 6500),
                        OrderLine("CRT", {"M": 10, "L": 10}, 20, 7500)], gstin=gstin, state_code=state_code)


def test_interstate_invoice_uses_igst_and_rounds_to_rupee():
    inv = make_invoice(order(), CAT, SHOP, number=1, date="2026-11-27")
    assert inv.place_of_supply == "32" and inv.interstate
    assert inv.taxable_paise == 24 * 6500 + 20 * 7500 == 306000
    assert inv.igst_paise == 15300 and inv.cgst_paise == inv.sgst_paise == 0
    assert inv.grand_total_paise == 321300 and inv.round_off_paise == 0
    assert inv.total_pcs == 44 and inv.b2b is False


def test_intrastate_invoice_splits_cgst_sgst():
    inv = make_invoice(order(city="Erode"), CAT, SHOP, number=2, date="2026-11-27")
    assert not inv.interstate and inv.igst_paise == 0
    assert inv.cgst_paise == inv.sgst_paise == 7650


def test_round_off_to_nearest_rupee():
    o = order(city="Erode")
    o.lines = [OrderLine("PRP", {}, 7, 6800)]  # 476.00 taxable, 2.5% = 11.90 each -> 499.80 -> 500
    inv = make_invoice(o, CAT, SHOP, number=3, date="2026-11-27")
    assert inv.grand_total_paise == 50000 and inv.round_off_paise == 20


def test_gstin_decides_state_and_b2b():
    inv = make_invoice(order(city=None, gstin="32AAKFL4333R1ZX"), CAT, SHOP, number=4, date="2026-11-27")
    assert inv.b2b and inv.place_of_supply == "32" and inv.igst_paise > 0


def test_unknown_place_of_supply_raises():
    with pytest.raises(ValueError, match="state"):
        make_invoice(order(city="Atlantis"), CAT, SHOP, number=5, date="2026-11-27")


def test_rate_above_2500_is_18_percent():
    o = order(city="Erode")
    o.lines = [OrderLine("PPL", {}, 1, 300000)]
    inv = make_invoice(o, CAT, SHOP, number=6, date="2026-11-27")
    assert inv.cgst_paise == inv.sgst_paise == 27000 and inv.lines[0].gst_pct == 18


def test_lines_show_sizes_like_the_shop_writes_them():
    inv = make_invoice(order(), CAT, SHOP, number=1, date="2026-11-27")
    first = inv.lines[0]
    assert (first.sno, first.name, first.hsn, first.size, first.qty) == (1, "Plain palazzo", "6104", "S, M, L, XL", 24)


def test_invoice_number_has_financial_year():
    assert invoice_number("KG", 7, "2026-11-27") == "KG/26-27/0007"
    assert invoice_number("KG", 1, "2027-03-31") == "KG/26-27/0001"
    assert invoice_number("KG", 1, "2027-04-01") == "KG/27-28/0001"


def test_amount_in_words_indian_system():
    assert amount_in_words(460138) == "Four Lakh Sixty Thousand One Hundred Thirty Eight Rupees Only"
    assert amount_in_words(3213) == "Three Thousand Two Hundred Thirteen Rupees Only"
    assert amount_in_words(10000000) == "One Crore Rupees Only"


def test_state_code_for():
    assert state_code_for("32AAKFL4333R1ZX", None) == "32"
    assert state_code_for(None, "Manjeri") == "32"
    assert state_code_for(None, "Tirupur") == "33"
    assert state_code_for(None, "Bengaluru") == "29"
    assert state_code_for(None, "Nowhere") is None


def test_packing_list_one_row_per_size():
    rows = packing_list(order(), CAT)
    assert rows[:2] == [("Plain palazzo", "S", 6), ("Plain palazzo", "M", 6)] and len(rows) == 6


def test_share_text_is_a_tax_invoice():
    text = share_text(make_invoice(order(), CAT, SHOP, number=12, date="2026-11-27"), {"name": "KURAL GARMENTS (DEMO)"})
    assert text.startswith("TAX INVOICE KG/26-27/0012")
    assert "IGST 5%" in text and "Grand total ₹3,213" in text and "Three Thousand Two Hundred Thirteen" in text
