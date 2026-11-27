import copy

import pytest

from app.domain.catalog import Catalog
from app.domain.changes import AddLine, ChangeLine, SetField
from app.domain.order import Order, apply_changes
from app.domain.rules import compute_totals, missing_fields, normalise_payment


@pytest.fixture(scope="module")
def cat():
    return Catalog.load("data/items.json")


def empty_order():
    return Order(id=None, customer_name="Kerala Fancy", city="Palakkad", state="open",
                 transport=None, payment=None, lines=[])


def add(code, name, sizes=None, qty=None, rate=None):
    return AddLine(op="add_line", item_code=code, name_as_spoken=name, sizes=sizes or {},
                   quantity_total=qty, rate_spoken=rate)


PIECE1 = [add("PRP", "print palazzo", qty=24), add("CRT", "crop top", sizes={"S": 6, "M": 6, "L": 6})]
PIECE2 = [add("KPS", "kids palazzo set", sizes={"S": 10, "M": 10, "L": 10}),
          ChangeLine(op="change_line", item_code="CRT", sizes={"S": 12, "M": 12, "L": 12})]


def line(order, code):
    return next(l for l in order.lines if l.item_code == code)


def test_new_order_from_piece1(cat):
    res = apply_changes(empty_order(), PIECE1, cat)
    assert [l.item_code for l in res.order.lines] == ["PRP", "CRT"]
    assert [d.kind for d in res.diff] == ["added", "added"]
    assert res.problems == []
    t = compute_totals(res.order, cat)
    assert (t.subtotal_paise, t.gst_paise, t.total_paise) == (298200, 14910, 313110)


def test_piece2_merges_and_changes(cat):
    o = apply_changes(empty_order(), PIECE1, cat).order
    res = apply_changes(o, PIECE2, cat)
    assert len(res.order.lines) == 3
    assert line(res.order, "CRT").quantity == 36
    assert [d.kind for d in res.diff] == ["added", "changed"]
    t = compute_totals(res.order, cat)
    assert (t.subtotal_paise, t.gst_paise, t.total_paise) == (793200, 39660, 832860)


def test_same_item_added_twice_merges(cat):
    o = apply_changes(empty_order(), [add("CRT", "crop top", sizes={"S": 6, "M": 6})], cat).order
    res = apply_changes(o, [add(None, "crop tops", sizes={"M": 6, "L": 6})], cat)
    assert len(res.order.lines) == 1
    assert line(res.order, "CRT").sizes == {"S": 6, "M": 12, "L": 6}
    assert line(res.order, "CRT").quantity == 24
    assert res.diff[0].kind == "changed"


def test_unknown_item_reported_not_added(cat):
    res = apply_changes(empty_order(), [add(None, "silk saree", qty=10)], cat)
    assert res.order.lines == []
    assert res.problems == ["Unknown item: silk saree"]


def test_size_zero_removes_size(cat):
    o = apply_changes(empty_order(), PIECE1, cat).order
    res = apply_changes(o, [ChangeLine(op="change_line", item_code="CRT", sizes={"L": 0})], cat)
    assert line(res.order, "CRT").sizes == {"S": 6, "M": 6}
    assert line(res.order, "CRT").quantity == 12


def test_change_line_not_in_order(cat):
    res = apply_changes(empty_order(), [ChangeLine(op="change_line", item_code="KPS", quantity_total=5)], cat)
    assert res.problems == ["Not in order: KPS"]


def test_below_min_flag(cat):
    o = apply_changes(empty_order(), [add("CRT", "crop top", sizes={"S": 4}), add("PRP", "print palazzo", qty=20),
                                      add("KPS", "kids palazzo set", qty=30)], cat).order
    assert "below_min" in line(o, "CRT").flags
    assert "below_min" in line(o, "PRP").flags
    assert "sizes_missing" in line(o, "KPS").flags


def test_rate_off_list_flag(cat):
    off = apply_changes(empty_order(), [add("PRP", "print palazzo", qty=24, rate=58)], cat).order
    near = apply_changes(empty_order(), [add("PRP", "print palazzo", qty=24, rate=70)], cat).order
    assert "rate_off_list" in line(off, "PRP").flags
    assert line(off, "PRP").rate_paise == 5800
    assert "rate_off_list" not in line(near, "PRP").flags


def test_gst_18_percent_above_2500(cat):
    o = apply_changes(empty_order(), [add("PRP", "print palazzo", qty=1, rate=3000)], cat).order
    assert compute_totals(o, cat).gst_paise == 54000


def test_missing_fields(cat):
    o = apply_changes(empty_order(), PIECE1, cat).order
    assert missing_fields(o) == ["transport", "payment"]
    o = apply_changes(o, [SetField(op="set_field", field="transport", value="KPN"),
                          SetField(op="set_field", field="payment", value="credit")], cat).order
    assert missing_fields(o) == []
    assert (o.transport, o.payment) == ("KPN", "credit")


def test_unclear_payment_is_a_problem(cat):
    res = apply_changes(empty_order(), [SetField(op="set_field", field="payment", value="later maybe")], cat)
    assert res.problems == ["Unclear payment: later maybe"]
    assert res.order.payment is None


def test_normalise_payment():
    assert normalise_payment("Kadan") == "credit"
    assert normalise_payment("udhaar") == "credit"
    assert normalise_payment("GPay") == "upi"
    assert normalise_payment("cash") == "cash"
    assert normalise_payment("account transfer") == "bank"
    assert normalise_payment("tomorrow") is None


def test_apply_is_pure(cat):
    o = apply_changes(empty_order(), PIECE1, cat).order
    before = copy.deepcopy(o)
    apply_changes(o, PIECE2, cat)
    assert o == before


def test_unsized_add_to_sized_line_is_a_problem(cat):
    o = apply_changes(empty_order(), [add("CRT", "crop top", sizes={"S": 6, "M": 6})], cat).order
    res = apply_changes(o, [add("CRT", "crop top", qty=6)], cat)
    assert res.problems == ["Sizes needed for: Crop top"]
    assert line(res.order, "CRT").quantity == 12


def test_sized_add_to_unsized_line_is_a_problem(cat):
    o = apply_changes(empty_order(), [add("PRP", "print palazzo", qty=24)], cat).order
    res = apply_changes(o, [add("PRP", "print palazzo", sizes={"S": 10})], cat)
    assert res.problems == ["Sizes don't match for: Print palazzo"]
    assert line(res.order, "PRP").quantity == 24


def test_total_change_on_sized_line_is_a_problem(cat):
    o = apply_changes(empty_order(), [add("CRT", "crop top", sizes={"S": 6, "M": 6})], cat).order
    res = apply_changes(o, [ChangeLine(op="change_line", item_code="CRT", quantity_total=30)], cat)
    assert res.problems == ["Sizes needed for: Crop top"]
    assert line(res.order, "CRT").quantity == 12


def test_item_code_contradicting_name_is_problem(cat):
    res = apply_changes(empty_order(), [add("GPT", "women's pant", qty=50)], cat)
    assert res.order.lines == []
    assert res.problems == ["Item code GPT does not match 'women's pant'"]


def test_unknown_item_offers_closest(cat):
    res = apply_changes(empty_order(), [add(None, "palazo set", qty=10)], cat)
    assert res.problems[0].startswith("Unknown item: palazo set. Closest: ")
    assert "Kids palazzo set" in res.problems[0]


def test_matching_code_and_name_still_added(cat):
    res = apply_changes(empty_order(), [add("GPT", "girls pant", sizes={"1-10 yrs": 50})], cat)
    assert res.problems == []
    assert line(res.order, "GPT").sizes == {"1-10 yrs": 50}
