def test_health(client):
    assert client.get("/health").json() == {"ok": True}


def test_status_not_set_without_keys(client, monkeypatch):
    monkeypatch.delenv("SARVAM_API_KEY", raising=False)
    assert client.get("/api/status").json()["providers"] == {
        "stt": "not_set", "llm": "not_set", "tts": "not_set"}


def test_status_ready_with_key(client, monkeypatch):
    monkeypatch.setenv("SARVAM_API_KEY", "x")
    assert client.get("/api/status").json()["providers"]["stt"] == "ready"


def test_main_screen_has_banner_text(client):
    html = client.get("/").text
    assert "Order Kural" in html
    assert "Sarvam API key not set: live voice is off." in html
