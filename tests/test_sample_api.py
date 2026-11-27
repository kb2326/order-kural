def run_sample(client, confirm=True):
    client.post("/api/sample/reset")
    pieces = []
    for _ in range(3):
        r = client.post("/api/sample/next")
        assert r.status_code == 200
        body = r.json()
        pieces.append(body)
        if confirm:
            assert client.post(f"/api/pieces/{body['proposal']['piece_id']}/confirm").status_code == 200
    return pieces


def test_sample_full_run(client):
    run_sample(client)
    orders = client.get("/api/orders").json()
    assert len(orders) == 1
    assert orders[0]["customer_name"] == "Kerala Fancy"
    assert orders[0]["total_paise"] == 832860
    assert orders[0]["total"] == "₹8,328.60"
    detail = client.get(f"/api/orders/{orders[0]['id']}").json()
    assert len(detail["lines"]) == 3
    assert detail["totals"]["total_paise"] == 832860


def test_sample_label_present(client):
    client.post("/api/sample/reset")
    body = client.post("/api/sample/next").json()
    assert body["label"] == "Sample: saved AI results"
    assert (body["index"], body["total"]) == (1, 3)
    assert body["transcript"]
    assert body["proposal"]["totals"]["total"] == "₹3,131.10"
    assert [d["kind"] for d in body["proposal"]["diff"]] == ["added", "added"]


def test_sample_finished_409(client):
    run_sample(client)
    r = client.post("/api/sample/next")
    assert r.status_code == 409
    assert r.json() == {"detail": "Sample finished"}


def test_confirm_twice_409(client):
    client.post("/api/sample/reset")
    pid = client.post("/api/sample/next").json()["proposal"]["piece_id"]
    assert client.post(f"/api/pieces/{pid}/confirm").status_code == 200
    assert client.post(f"/api/pieces/{pid}/confirm").status_code == 409


def test_discard_then_confirm_409(client):
    client.post("/api/sample/reset")
    pid = client.post("/api/sample/next").json()["proposal"]["piece_id"]
    assert client.post(f"/api/pieces/{pid}/discard").json() == {"ok": True}
    assert client.post(f"/api/pieces/{pid}/confirm").status_code == 409
    assert client.get("/api/orders").json() == []


def test_get_missing_order_404(client):
    assert client.get("/api/orders/999").status_code == 404
