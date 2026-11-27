import json
from pathlib import Path

import pytest

STEPS = 11


@pytest.fixture(autouse=True)
def sample_session(client, monkeypatch):
    monkeypatch.delenv("SARVAM_API_KEY", raising=False)  # the sample must work with no key at all
    client.headers["X-Sample-Session"] = "test-session-a"


def run_sample(client, upto=STEPS):
    client.post("/api/sample/reset")
    return [client.post("/api/sample/next").json() for _ in range(upto)]


def test_sample_runs_all_steps_without_key(client):
    steps = run_sample(client)
    assert [s["index"] for s in steps] == list(range(1, STEPS + 1)) and steps[0]["total"] == STEPS
    assert all(s["spoken"] for s in steps)
    assert steps[0]["label"] == "Sample: saved AI results · synthetic voice"
    assert "₹2,982" in steps[0]["spoken"][0] and steps[0]["slip"]["pending"]["customer"] == "Kerala Fancy"
    assert steps[3]["spoken"] == ["இது எந்த கஸ்டமருக்கு?"]


def test_sample_ends_with_bill_and_balance(client):
    steps = run_sample(client)
    assert steps[7]["bill_number"] == 1
    assert "₹1,911" in steps[9]["spoken"][0]  # 6,582 + 5% IGST = 6,911 invoiced - 5,000 paid
    assert "Sri Murugan Tex" in steps[10]["spoken"][0]
    bill = client.get("/api/bills/1").json()
    assert bill["customer"] == "Kerala Fancy" and bill["total"] == "₹6,911.00" and bill["interstate"]
    assert [c["name"] for c in client.get("/api/customers").json()] == ["Kerala Fancy", "Sri Murugan Tex"]


def test_sample_bill_page_uses_sample_session(client):
    run_sample(client)
    r = client.get("/bill/1?sample=test-session-a")
    assert r.status_code == 200 and "Kerala Fancy" in r.text


def test_sample_finished_409(client):
    run_sample(client)
    r = client.post("/api/sample/next")
    assert r.status_code == 409 and r.json() == {"detail": "Sample finished"}


def test_get_missing_order_404(client):
    assert client.get("/api/orders/999").status_code == 404


def test_two_sample_sessions_are_independent(client):
    run_sample(client, upto=3)
    r = client.post("/api/sample/next", headers={"X-Sample-Session": "test-session-b"})
    assert r.status_code == 200 and r.json()["index"] == 1


def test_sample_reset_does_not_touch_live_orders(client):
    from app.domain.order import Order
    live = client.app.state.pieces.store
    live.save_order(Order(id=None, customer_name="Real Shop", city="Erode", state="open",
                          transport=None, payment=None, lines=[]))
    run_sample(client)
    client.post("/api/sample/reset")
    del client.headers["X-Sample-Session"]
    names = [o["customer_name"] for o in client.get("/api/orders").json()]
    assert names == ["Real Shop"]


def test_sample_bot_audio_text_matches_say(client):
    """The pre-made bot audio must say exactly what the code says now, or the demo would contradict the screen."""
    texts_file = Path("app/sample/audio/say_texts.json")
    if not texts_file.exists():
        pytest.skip("sample audio not generated yet (scripts/make_sample_audio.py needs a key)")
    saved = json.loads(texts_file.read_text(encoding="utf-8"))
    steps = run_sample(client)
    assert [" ".join(s["spoken"]) for s in steps] == saved["bot"]


def test_books_keep_every_word_each_line_came_from(client):
    """The order book must show the words behind each line: all pieces merged into it, and the forwarded note."""
    run_sample(client)
    books = client.get("/api/books").json()
    kerala = next(o for o in books["orders"] if o["customer"] == "Kerala Fancy")
    said = kerala["lines"][0]["said"]
    assert "Print palazzo" in said and "kids palazzo set" in said  # piece 1 and piece 2, merged
    murugan = next(o for o in books["orders"] if o["customer"] == "Sri Murugan Tex")
    assert "Forwarded voice note from a buyer" in murugan["lines"][0]["said"]
