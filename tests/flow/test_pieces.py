import pytest

from app.domain.catalog import Catalog
from app.domain.changes import PieceResult
from app.domain.order import Order
from app.flow.pieces import PieceService, PieceStateError
from app.store.db import Store

P1 = {"intent": "order_changes",
      "customer": {"name_as_spoken": "Kerala Fancy", "city": "Palakkad", "match": "new"},
      "changes": [{"op": "add_line", "item_code": "PRP", "name_as_spoken": "print palazzo", "quantity_total": 24},
                  {"op": "add_line", "item_code": "CRT", "name_as_spoken": "crop top",
                   "sizes": {"S": 6, "M": 6, "L": 6}}]}
P2 = {"intent": "order_changes",
      "customer": {"name_as_spoken": "Kerala Fancy", "match": "existing"},
      "changes": [{"op": "add_line", "item_code": "KPS", "name_as_spoken": "kids palazzo set",
                   "sizes": {"S": 10, "M": 10, "L": 10}},
                  {"op": "change_line", "item_code": "CRT", "sizes": {"S": 12, "M": 12, "L": 12}}]}
P3 = {"intent": "order_changes",
      "customer": {"name_as_spoken": "Kerala Fancy", "match": "existing"},
      "changes": [{"op": "set_field", "field": "transport", "value": "KPN"},
                  {"op": "set_field", "field": "payment", "value": "credit"}]}


@pytest.fixture
def store(tmp_path):
    return Store(str(tmp_path / "sub" / "t.db"))


@pytest.fixture
def svc(store):
    return PieceService(store, Catalog.load("data/items.json"))


def run(svc, raw, transcript="t"):
    return svc.propose(transcript, PieceResult.model_validate(raw), source="sample")


def test_three_pieces_build_one_order(svc, store):
    ids = []
    for raw in (P1, P2, P3):
        p = run(svc, raw)
        ids.append(p.piece_id)
        svc.confirm(p.piece_id)
    orders = store.open_orders()
    assert len(orders) == 1
    o = orders[0]
    assert (o.customer_name, len(o.lines), o.transport, o.payment) == ("Kerala Fancy", 3, "KPN", "credit")
    from app.domain.rules import compute_totals
    assert compute_totals(o, svc.catalog).total_paise == 832860


def test_nothing_applied_before_confirm(svc, store):
    p = run(svc, P1)
    assert store.open_orders() == []
    assert store.get_piece(p.piece_id)["state"] == "read_back"


def test_confirm_twice_raises(svc):
    p = run(svc, P1)
    svc.confirm(p.piece_id)
    with pytest.raises(PieceStateError):
        svc.confirm(p.piece_id)


def test_confirm_discarded_raises(svc, store):
    p = run(svc, P1)
    svc.discard(p.piece_id)
    assert store.get_piece(p.piece_id)["state"] == "discarded"
    with pytest.raises(PieceStateError):
        svc.confirm(p.piece_id)
    assert store.open_orders() == []


def test_billed_customer_starts_new_order(svc, store):
    store.save_order(Order(id=None, customer_name="Kerala Fancy", city="Palakkad", state="billed",
                           transport="KPN", payment="credit", lines=[]))
    p = run(svc, P2)
    assert p.is_new_order is True
    assert p.order_id is None


def test_existing_open_order_is_targeted(svc):
    first = run(svc, P1)
    svc.confirm(first.piece_id)
    p = run(svc, P2)
    assert p.is_new_order is False
    assert p.order_id is not None


def test_low_confidence_asks_customer(svc, store):
    raw = {**P2, "customer": {"name_as_spoken": "Kerala", "match": "existing", "confidence": "low"}}
    p = run(svc, raw)
    assert p.ask_customer is True
    with pytest.raises(PieceStateError):
        svc.confirm(p.piece_id)


def test_lines_record_source_piece(svc, store):
    ids = []
    for raw in (P1, P2, P3):
        p = run(svc, raw)
        ids.append(p.piece_id)
        svc.confirm(p.piece_id)
    o = store.open_orders()[0]
    src = {l.item_code: l.source_piece_id for l in o.lines}
    assert src == {"PRP": ids[0], "CRT": ids[1], "KPS": ids[1]}


def test_readback_piece1_text(svc):
    p = run(svc, P1)
    assert p.readback == ("Kerala Fancy, Palakkad. Added: Print palazzo 24 at ₹68. "
                          "Added: Crop top S 6, M 6, L 6 at ₹75. Order total ₹3,131.10 with GST. "
                          "Still needed: transport, payment. Say sari to confirm.")


# ---- final-review fixes ----------------------------------------------------------------------------------------
import threading
import time


def test_unsupported_intent_cannot_be_confirmed(svc, store):
    raw = {**P1, "intent": "unclear"}
    p = run(svc, raw)
    with pytest.raises(PieceStateError):
        svc.confirm(p.piece_id)
    assert store.open_orders() == []


def test_piece_with_nothing_to_apply_cannot_be_confirmed(svc, store):
    raw = {**P1, "changes": [{"op": "add_line", "name_as_spoken": "silk saree", "quantity_total": 5}]}
    p = run(svc, raw)
    assert p.problems == ["Unknown item: silk saree"]
    with pytest.raises(PieceStateError):
        svc.confirm(p.piece_id)
    assert store.open_orders() == []


def test_confirm_is_atomic(svc, store, monkeypatch):
    p = run(svc, P1)

    def boom(*a, **k):
        raise RuntimeError("disk full")
    monkeypatch.setattr(store, "add_event", boom)
    with pytest.raises(RuntimeError):
        svc.confirm(p.piece_id)
    assert store.open_orders() == []
    assert store.get_piece(p.piece_id)["state"] == "read_back"


def test_concurrent_confirms_apply_once(svc, store, monkeypatch):
    first = run(svc, P1)
    svc.confirm(first.piece_id)
    p = run(svc, P2)
    real_save = store.save_order

    def slow_save(order):
        time.sleep(0.2)
        return real_save(order)
    monkeypatch.setattr(store, "save_order", slow_save)
    results = []

    def go():
        try:
            svc.confirm(p.piece_id)
            results.append("ok")
        except PieceStateError:
            results.append("409")
    threads = [threading.Thread(target=go) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(results) == ["409", "ok"]
    kps = next(l for l in store.open_orders()[0].lines if l.item_code == "KPS")
    assert kps.quantity == 30


def test_same_name_other_city_starts_new_order(svc, store):
    a = run(svc, {**P1, "customer": {"name_as_spoken": "Ravi Textiles", "city": "Salem"}})
    svc.confirm(a.piece_id)
    p = run(svc, {**P1, "customer": {"name_as_spoken": "Ravi Textiles", "city": "Erode"}})
    assert p.is_new_order is True


def test_two_open_orders_same_name_asks_customer(svc, store):
    for city in ("Salem", "Erode"):
        a = run(svc, {**P1, "customer": {"name_as_spoken": "Ravi Textiles", "city": city}})
        svc.confirm(a.piece_id)
    p = run(svc, {**P3, "customer": {"name_as_spoken": "Ravi Textiles", "match": "existing"}})
    assert p.ask_customer is True
