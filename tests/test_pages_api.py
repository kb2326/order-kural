import pytest

from app.agent.session import AgentSession
from app.flow.shop import ShopService

PALAZZO = [{"name_as_spoken": "plain palazzo", "item_code": "PPL", "sizes": {"S": 6, "M": 6}}]


@pytest.fixture
def billed(client):
    """A live order for Kerala Fancy, billed (bill 1), with a ₹500 UPI payment."""
    live = client.app.state.pieces
    agent = AgentSession(live, ShopService(live.store, live.catalog))
    agent.heard("Kerala Fancy palazzo", "en-IN")
    agent.add_to_order("Kerala Fancy", PALAZZO)
    for step in (lambda: None, lambda: agent.bill_order("Kerala Fancy"),
                 lambda: agent.record_payment("Kerala Fancy", 500, "upi")):
        step()
        agent.heard("sari")
        agent.confirm_pending()
    return client


def test_bill_json_has_lines_packing_and_share_text(billed):
    r = billed.get("/api/bills/1")
    assert r.status_code == 200
    b = r.json()
    assert b["number"] == 1 and b["customer"] == "Kerala Fancy" and b["total"] == "₹780.00"
    assert b["lines"][0]["name"] == "Plain palazzo" and b["lines"][0]["amount"] == "₹780.00"
    assert b["packing"] == [{"item": "Plain palazzo", "size": "S", "qty": 6},
                            {"item": "Plain palazzo", "size": "M", "qty": 6}]
    assert b["share_text"].startswith("Order bill (estimate) No. 1")


def test_missing_bill_404(client):
    assert client.get("/api/bills/99").status_code == 404


def test_bill_page_has_estimate_title_and_no_gst(billed):
    r = billed.get("/bill/1")
    assert r.status_code == 200 and "text/html" in r.headers["content-type"]
    assert "Order bill (estimate)" in r.text and "Tax as per final invoice" in r.text
    assert "GST" not in r.text and "Packing list" in r.text


def test_bills_list(billed):
    assert [b["number"] for b in billed.get("/api/bills").json()] == [1]


def test_customers_list_balances(billed):
    rows = billed.get("/api/customers").json()
    assert rows == [{"id": rows[0]["id"], "name": "Kerala Fancy", "city": None, "balance_paise": 28000,
                     "balance": "₹280.00"}]


def test_khata_entries(billed):
    cid = billed.get("/api/customers").json()[0]["id"]
    k = billed.get(f"/api/customers/{cid}/khata").json()
    assert [e["kind"] for e in k["entries"]] == ["bill", "payment"] and k["balance_paise"] == 28000


def test_undo_endpoint(billed):
    cid = billed.get("/api/customers").json()[0]["id"]
    r = billed.post(f"/api/customers/{cid}/undo")
    assert r.status_code == 200 and r.json()["message"] == "Payment of ₹500.00 undone"
    assert billed.get("/api/customers").json()[0]["balance_paise"] == 78000


def test_undo_nothing_409(client):
    live = client.app.state.pieces
    cid = live.store.save_order.__self__._customer_id("Nobody", None)
    assert client.post(f"/api/customers/{cid}/undo").status_code == 409


def test_live_orders_listed_without_sample_header(billed):
    assert billed.get("/api/orders").json() == []  # the billed order is no longer open
    assert [o["customer"] for o in billed.get("/api/to-ship").json()["orders"]] == ["Kerala Fancy"]
