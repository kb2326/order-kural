from datetime import datetime, timedelta, timezone

import pytest

from app.domain.catalog import Catalog
from app.domain.order import Order, OrderLine
from app.flow import ask
from app.flow.shop import ShopService
from app.store.db import Store

CAT = Catalog.load("data/items.json")
NOW = datetime(2026, 11, 27, 12, 0, tzinfo=timezone.utc)


@pytest.fixture
def store():
    return Store(":memory:")


def save(store, name, lines, state="open"):
    return store.save_order(Order(None, name, None, state, None, None, lines))


def test_to_ship_lists_open_and_billed_not_shipped(store):
    shop = ShopService(store, CAT)
    a = save(store, "Kerala Fancy", [OrderLine("PPL", {"S": 6}, 6, 6500)])
    b = save(store, "Sri Murugan", [OrderLine("CRT", {"M": 10}, 10, 7500)])
    c = save(store, "Lakshmi Tex", [OrderLine("GPT", {}, 24, 5500)])
    shop.issue_bill(b)
    shop.issue_bill(c)
    shop.mark_shipped(c, "KPN")
    answer = ask.to_ship(store, CAT)
    assert answer.kind == "to_ship"
    rows = answer.facts["orders"]
    assert [r["customer"] for r in rows] == ["Kerala Fancy", "Sri Murugan"]
    assert rows[0]["bill_number"] is None and rows[1]["bill_number"] == 1
    assert rows[1]["total_paise"] == 75000 and rows[1]["lines"] == 1


def test_customer_summary_has_balance(store):
    shop = ShopService(store, CAT)
    billed = save(store, "Kerala Fancy", [OrderLine("PPL", {"S": 6}, 6, 6500)])
    shop.issue_bill(billed)
    customer_id = store.customer_id_of_order(billed)
    save(store, "Kerala Fancy", [OrderLine("CRT", {"M": 10}, 10, 7500)])
    shop.record_payment(customer_id, 10000, "upi")
    answer = ask.customer_summary(store, CAT, customer_id)
    assert answer.facts["customer"] == "Kerala Fancy"
    assert answer.facts["balance_paise"] == 6 * 6500 - 10000
    assert answer.facts["open_lines"] == [{"item": "Crop top", "qty": "M 10"}]


def test_item_count_last_7_days_only(store):
    recent = save(store, "Kerala Fancy", [OrderLine("GPT", {"1-10 yrs": 50}, 50, 5500)])
    old = save(store, "Sri Murugan", [OrderLine("GPT", {}, 24, 5500)])
    cancelled = save(store, "Lakshmi Tex", [OrderLine("GPT", {}, 10, 5500)], state="cancelled")
    stamp = (NOW - timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
    store.conn.execute("UPDATE orders SET created_at=? WHERE id IN (?, ?)", (stamp, recent, cancelled))
    store.conn.execute("UPDATE orders SET created_at=? WHERE id=?",
                       ((NOW - timedelta(days=9)).strftime("%Y-%m-%d %H:%M:%S"), old))
    answer = ask.item_count(store, CAT, "GPT", now=NOW)
    assert answer.facts == {"item": "Girls pant", "quantity": 50, "days": 7}
