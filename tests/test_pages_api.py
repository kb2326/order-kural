import pytest

from app.agent.session import AgentSession
from app.flow.shop import ShopService

PALAZZO = [{"name_as_spoken": "plain palazzo", "item_code": "PPL", "sizes": {"S": 6, "M": 6}}]


@pytest.fixture
def billed(client):
    """A live order for Kerala Fancy (Kerala), invoiced (bill 1, IGST), with a ₹500 UPI payment."""
    live = client.app.state.pieces
    agent = AgentSession(live, ShopService(live.store, live.catalog))
    agent.heard("Kerala Fancy palazzo", "en-IN")
    agent.add_to_order("Kerala Fancy", PALAZZO, state="Kerala")
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
    assert b["number"] == 1 and b["customer"] == "Kerala Fancy" and b["total"] == "₹819.00"
    assert b["lines"][0]["name"] == "Plain palazzo" and b["lines"][0]["amount"] == "₹780.00"
    assert b["packing"] == [{"item": "Plain palazzo", "size": "S", "qty": 6},
                            {"item": "Plain palazzo", "size": "M", "qty": 6}]
    assert b["share_text"].startswith("TAX INVOICE KG/") and b["igst_paise"] == 3900
    assert b["tax_lines"] == [{"label": "IGST 5%", "amount": "₹39.00"}]
    assert b["amount_in_words"] == "Eight Hundred Nineteen Rupees Only"


def test_missing_bill_404(client):
    assert client.get("/api/bills/99").status_code == 404


def test_bill_page_is_a_tax_invoice_in_the_shop_layout(billed):
    r = billed.get("/bill/1")
    assert r.status_code == 200 and "text/html" in r.headers["content-type"]
    for text in ("TAX INVOICE", "HSN Code", "IGST 5%", "Round off", "Grand Total", "Eight Hundred Nineteen Rupees Only",
                 "Unregistered (B2C)", "KURAL GARMENTS (DEMO)", "Authorised Signatory", "Packing list"):
        assert text in r.text, text
    assert "estimate" not in r.text.lower()


def test_bills_list(billed):
    assert [b["number"] for b in billed.get("/api/bills").json()] == [1]


def test_customers_list_balances(billed):
    rows = billed.get("/api/customers").json()
    assert rows == [{"id": rows[0]["id"], "name": "Kerala Fancy", "city": None, "balance_paise": 31900,
                     "balance": "₹319.00"}]


def test_khata_entries(billed):
    cid = billed.get("/api/customers").json()[0]["id"]
    k = billed.get(f"/api/customers/{cid}/khata").json()
    assert [e["kind"] for e in k["entries"]] == ["bill", "payment"] and k["balance_paise"] == 31900


def test_undo_endpoint(billed):
    cid = billed.get("/api/customers").json()[0]["id"]
    r = billed.post(f"/api/customers/{cid}/undo")
    assert r.status_code == 200 and r.json()["message"] == "Payment of ₹500.00 undone"
    assert billed.get("/api/customers").json()[0]["balance_paise"] == 81900


def test_undo_nothing_409(client):
    live = client.app.state.pieces
    cid = live.store.save_order.__self__._customer_id("Nobody", None)
    assert client.post(f"/api/customers/{cid}/undo").status_code == 409


def test_live_orders_listed_without_sample_header(billed):
    assert billed.get("/api/orders").json() == []  # the billed order is no longer open
    assert [o["customer"] for o in billed.get("/api/to-ship").json()["orders"]] == ["Kerala Fancy"]


def test_monthly_gst_report_for_the_auditor(billed):
    r = billed.get("/api/reports/gst.csv?month=" + billed.get("/api/bills/1").json()["date"][:7])
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    lines = r.text.strip().splitlines()
    assert lines[0].startswith("Invoice no,Date,Buyer,Buyer GSTIN,Type,Place of supply")
    row = lines[1].split(",")
    assert row[2] == "Kerala Fancy" and row[4] == "B2C" and row[5] == "32" and "780.00" in row and "39.00" in row


def test_gst_report_skips_voided_and_other_months(billed):
    cid = billed.get("/api/customers").json()[0]["id"]
    billed.post(f"/api/customers/{cid}/undo")  # the payment
    billed.post(f"/api/customers/{cid}/undo")  # the invoice -> voided
    month = billed.get("/api/bills/1").json()["date"][:7]
    assert len(billed.get(f"/api/reports/gst.csv?month={month}").text.strip().splitlines()) == 1
    assert len(billed.get("/api/reports/gst.csv?month=1999-01").text.strip().splitlines()) == 1


def test_gst_report_bad_month_422(client):
    assert client.get("/api/reports/gst.csv?month=Nov").status_code == 422


def test_open_orders_list_shows_value_before_gst(client):
    live = client.app.state.pieces
    agent = AgentSession(live, ShopService(live.store, live.catalog))
    agent.heard("Kerala Fancy palazzo", "en-IN")
    agent.add_to_order("Kerala Fancy", PALAZZO)
    agent.heard("sari")
    agent.confirm_pending()
    [row] = client.get("/api/orders").json()
    assert row["total_paise"] == 78000 and row["total"] == "₹780.00"  # GST is added only on the invoice
