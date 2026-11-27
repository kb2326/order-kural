"""Tests for the final whole-branch review findings (27 Nov). Each one failed before its fix."""
import threading

import pytest

from app.agent import say
from app.agent.session import AgentSession
from app.domain.catalog import Catalog
from app.flow.pieces import PieceService
from app.flow.shop import ShopError, ShopService
from app.store.db import Store

CAT = Catalog.load("data/items.json")
PALAZZO = [{"name_as_spoken": "plain palazzo", "item_code": "PPL", "sizes": {"S": 6, "M": 6}}]


@pytest.fixture
def store():
    return Store(":memory:")


@pytest.fixture
def agent(store):
    a = AgentSession(PieceService(store, CAT), ShopService(store, CAT))
    a.heard("Kerala Fancy palazzo", "ta-IN")
    return a


def saved_order(agent):
    agent.add_to_order("Kerala Fancy", PALAZZO, state="Kerala")
    agent.heard("sari", "ta-IN")
    agent.confirm_pending()


# C1: one "sari" approves exactly one thing that was read back before it.
def test_one_sari_cannot_also_confirm_a_bill_staged_after_it(agent, store):
    saved_order(agent)
    agent.call("bill_order", {"customer": "Kerala Fancy"})          # same reply as the confirm, after "sari"
    r = agent.call("confirm_pending", {})
    assert r.say == say.render("need_yes", {"customer": "Kerala Fancy"}, "ta-IN")
    assert store.get_bill(1) is None


def test_staging_and_confirming_in_the_same_turn_is_refused(agent, store):
    agent.heard("Ravi shirts ok", "en-IN")                           # short and contains a yes word
    agent.call("add_to_order", {"customer": "Ravi Tex", "items": PALAZZO})
    r = agent.call("confirm_pending", {})
    assert r.say.startswith("Say sari") and store.open_orders() == []


def test_a_later_sari_still_confirms(agent, store):
    saved_order(agent)
    agent.call("bill_order", {"customer": "Kerala Fancy"})
    agent.heard("சரி", "ta-IN")
    agent.call("confirm_pending", {})
    assert store.get_bill(1) is not None


# I1: shipping before billing.
def test_shipping_an_unbilled_order_asks_to_bill_first(agent, store):
    saved_order(agent)
    r = agent.mark_shipped("Kerala Fancy", "KPN")
    assert agent.pending is None and "bill" in r.say.lower()


# I2: undoing the invoice of a shipped order.
def test_undo_invoice_of_shipped_order_is_refused(store):
    shop = ShopService(store, CAT)
    from app.domain.order import Order, OrderLine
    oid = store.save_order(Order(None, "Kerala Fancy", "Palakkad", "open", None, None,
                                 [OrderLine("PPL", {"S": 6}, 6, 6500)]))
    shop.issue_bill(oid)
    shop.mark_shipped(oid, "KPN")
    with pytest.raises(ShopError, match="shipped"):
        shop.undo_last(store.customer_id_of_order(oid))
    assert store.get_order(oid).state == "shipped" and store.get_bill(1)["voided"] == 0


# I3: decimal payment amounts.
def test_decimal_payment_is_exact_paise(agent, store):
    saved_order(agent)
    agent.heard("bill it", "ta-IN")
    agent.bill_order("Kerala Fancy")
    agent.heard("sari", "ta-IN")
    agent.confirm_pending()
    agent.heard("paid 500.50 upi", "en-IN")
    r = agent.call("record_payment", {"customer": "Kerala Fancy", "amount_rupees": 500.5, "mode": "upi"})
    assert "₹500.50" in r.say
    agent.heard("sari", "en-IN")
    agent.confirm_pending()
    entry = store.ledger_for(store.find_customers("Kerala Fancy")[0]["id"])[-1]
    assert entry["amount_paise"] == 50050 and isinstance(entry["amount_paise"], int)


def test_bad_amount_is_a_spoken_problem_not_a_crash(agent):
    saved_order(agent)
    r = agent.call("record_payment", {"customer": "Kerala Fancy", "amount_rupees": "lots", "mode": "upi"})
    assert agent.pending is None and ("error" in r.facts or "Amount" in r.say)


# I7: one lock per session.
def test_session_calls_are_serialised(agent):
    assert isinstance(agent.lock, type(threading.RLock()))


# Re-graded: a repeated identical call is not spoken twice.
def test_repeated_call_is_marked_so_it_is_not_spoken_again(agent):
    first = agent.call("add_to_order", {"customer": "Kerala Fancy", "items": PALAZZO})
    again = agent.call("add_to_order", {"customer": "Kerala Fancy", "items": PALAZZO})
    assert not first.repeat and again.repeat


# Minor fixed in passing: a zero balance is "settled", not "still owes Rs 0".
def test_zero_balance_payment_is_settled():
    text = say.render("payment_saved", {"customer": "Kerala Fancy", "balance_paise": 0}, "en-IN")
    assert "settled" in text and "owes" not in text


def test_invoice_date_is_india_time(monkeypatch):
    """The container clock is UTC: at 20:00 UTC it is already the next day in India."""
    from datetime import datetime, timezone
    import app.flow.shop as shop_mod

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 11, 30, 20, 0, tzinfo=timezone.utc).astimezone(tz)

    monkeypatch.setattr(shop_mod, "datetime", Clock)
    assert shop_mod.today_ist() == "2026-12-01"
