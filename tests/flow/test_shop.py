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


def test_issue_bill_twice_raises(store, shop):
    oid = saved_order(store)
    shop.issue_bill(oid)
    with pytest.raises(ShopError):
        shop.issue_bill(oid)
