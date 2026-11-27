import pytest

from app.domain.catalog import Catalog
from app.domain.order import Order, OrderLine
from app.flow.shop import ShopError, ShopService
from app.store.db import Store

CAT = Catalog.load("data/items.json")


@pytest.fixture
def store():
    return Store(":memory:")


@pytest.fixture
def shop(store):
    return ShopService(store, CAT)


def saved_order(store, name="Kerala Fancy", lines=None):
    lines = [OrderLine("PPL", {"S": 6, "M": 6}, 12, 6500)] if lines is None else lines
    return store.save_order(Order(None, name, "Palakkad", "open", None, "credit", lines))


def test_issue_bill_numbers_increase_and_lock_order(store, shop):
    a, b = saved_order(store), saved_order(store, "Sri Murugan")
    first, second = shop.issue_bill(a), shop.issue_bill(b)
    assert (first.number, second.number) == (1, 2)
    assert first.total_paise == 12 * 6500
    assert store.get_order(a).state == "billed"
    assert a not in [o.id for o in store.open_orders()]
    assert store.get_bill(1)["order_id"] == a


def test_issue_bill_empty_order_raises(store, shop):
    oid = saved_order(store, lines=[])
    with pytest.raises(ShopError, match="Nothing to bill for Kerala Fancy"):
        shop.issue_bill(oid)
    assert store.get_order(oid).state == "open"


def cid(store, order_id):
    return store.customer_id_of_order(order_id)


def test_bill_adds_khata_debit(store, shop):
    oid = saved_order(store)
    bill = shop.issue_bill(oid)
    assert shop.balance(cid(store, oid)) == bill.total_paise


def test_balance_bill_minus_payment(store, shop):
    oid = saved_order(store)
    shop.issue_bill(oid)
    assert shop.record_payment(cid(store, oid), 50000, "upi") == 12 * 6500 - 50000


def test_overpayment_gives_negative_balance(store, shop):
    oid = saved_order(store)
    shop.issue_bill(oid)
    assert shop.record_payment(cid(store, oid), 100000, "cash") == 12 * 6500 - 100000 < 0


def test_undo_payment_restores_balance(store, shop):
    oid = saved_order(store)
    shop.issue_bill(oid)
    shop.record_payment(cid(store, oid), 50000, "upi")
    assert shop.undo_last(cid(store, oid)) == "Payment of ₹500.00 undone"
    assert shop.balance(cid(store, oid)) == 12 * 6500


def test_undo_bill_voids_and_reopens_order(store, shop):
    oid = saved_order(store)
    shop.issue_bill(oid)
    assert shop.undo_last(cid(store, oid)) == "Bill 1 undone"
    assert store.get_bill(1)["voided"] == 1
    assert store.get_order(oid).state == "open"
    assert shop.balance(cid(store, oid)) == 0


def test_undo_twice_reverses_previous_entry_not_the_reversal(store, shop):
    oid = saved_order(store)
    shop.issue_bill(oid)
    shop.record_payment(cid(store, oid), 50000, "upi")
    shop.undo_last(cid(store, oid))
    assert shop.undo_last(cid(store, oid)) == "Bill 1 undone"
    assert shop.balance(cid(store, oid)) == 0
    with pytest.raises(ShopError, match="Nothing to undo"):
        shop.undo_last(cid(store, oid))


def test_mark_shipped_sets_state_and_transport(store, shop):
    oid = saved_order(store)
    shop.issue_bill(oid)
    shop.mark_shipped(oid, "KPN")
    order = store.get_order(oid)
    assert order.state == "shipped" and order.transport == "KPN"


def test_issue_bill_twice_raises(store, shop):
    oid = saved_order(store)
    shop.issue_bill(oid)
    with pytest.raises(ShopError):
        shop.issue_bill(oid)
