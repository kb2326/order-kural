from dataclasses import fields

from app.domain.bill import Bill, make_bill, packing_list, share_text
from app.domain.catalog import Catalog
from app.domain.order import Order, OrderLine

CAT = Catalog.load("data/items.json")


def order():
    return Order(id=5, customer_name="Kerala Fancy", city="Palakkad", state="open", transport="KPN", payment="credit",
                 lines=[OrderLine("PPL", {"S": 6, "M": 6, "L": 6, "XL": 6}, 24, 6500),
                        OrderLine("CRT", {"M": 10, "L": 10}, 20, 7500)])


def test_bill_amounts_no_gst():
    bill = make_bill(order(), CAT, number=1, created_at="2026-11-27")
    assert bill.total_paise == 24 * 6500 + 20 * 7500
    assert [l.amount_paise for l in bill.lines] == [24 * 6500, 20 * 7500]
    assert bill.lines[0].name == "Plain palazzo" and bill.lines[0].hsn
    assert not any("gst" in f.name for f in fields(Bill))


def test_packing_list_one_row_per_size():
    rows = packing_list(order(), CAT)
    assert rows[:4] == [("Plain palazzo", "S", 6), ("Plain palazzo", "M", 6), ("Plain palazzo", "L", 6),
                        ("Plain palazzo", "XL", 6)]
    assert len(rows) == 6


def test_packing_list_unsized_line_uses_dash():
    o = order()
    o.lines = [OrderLine("PRP", {}, 24, 6800)]
    assert packing_list(o, CAT) == [("Print palazzo", "-", 24)]


def test_share_text_has_estimate_title_and_footer():
    text = share_text(make_bill(order(), CAT, number=12, created_at="2026-11-27"))
    assert text.startswith("Order bill (estimate) No. 12")
    assert "Kerala Fancy" in text and "Total ₹3,060" in text
    assert text.rstrip().endswith("Tax as per final invoice")
    assert "GST" not in text
