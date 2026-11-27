import json

import httpx
import pytest

from app.ratelimit import RateLimiter

H = {"X-Agent-Session": "agent-test-1"}
ADD = {"choices": [{"message": {"role": "assistant", "content": None, "tool_calls": [
    {"id": "c1", "type": "function", "function": {"name": "add_to_order", "arguments": json.dumps(
        {"customer": "Kerala Fancy", "items": [{"name_as_spoken": "plain palazzo", "item_code": "PPL",
                                                "sizes": {"S": 6, "M": 6}}]})}}]}}],
    "usage": {"prompt_tokens": 10, "completion_tokens": 5}}


@pytest.fixture
def keyed(client, monkeypatch):
    monkeypatch.setenv("SARVAM_API_KEY", "test-key")
    client.app.state.llm_client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json=ADD)))
    return client


def test_text_endpoint_503_without_key(client, monkeypatch):
    monkeypatch.delenv("SARVAM_API_KEY", raising=False)
    r = client.post("/api/agent/text", json={"text": "hello"}, headers=H)
    assert r.status_code == 503 and r.json()["detail"] == "Sarvam API key not set"


def test_text_turn_stages_order(keyed):
    r = keyed.post("/api/agent/text", json={"text": "Kerala Fancy plain palazzo"}, headers=H)
    assert r.status_code == 200
    body = r.json()
    assert "₹780" in body["spoken"][0] and body["ui"]["pending"]["customer"] == "Kerala Fancy"


def test_tap_confirm_saves(keyed):
    keyed.post("/api/agent/text", json={"text": "Kerala Fancy plain palazzo"}, headers=H)
    r = keyed.post("/api/agent/confirm", headers=H)
    assert r.status_code == 200 and r.json()["ui"]["pending"] is None
    orders = keyed.get("/api/orders").json()
    assert [o["customer_name"] for o in orders] == ["Kerala Fancy"]


def test_tap_discard(keyed):
    keyed.post("/api/agent/text", json={"text": "Kerala Fancy plain palazzo"}, headers=H)
    assert keyed.post("/api/agent/discard", headers=H).json()["ui"]["pending"] is None
    assert keyed.get("/api/orders").json() == []


def test_rate_limit_429(keyed):
    keyed.app.state.text_limiter = RateLimiter(per_ip_hour=2, per_day=100)
    codes = [keyed.post("/api/agent/text", json={"text": "x"}, headers=H).status_code for _ in range(3)]
    assert codes == [200, 200, 429]


def test_rate_limiter_counts_per_ip_and_day():
    now = [0.0]
    rl = RateLimiter(per_ip_hour=2, per_day=3, clock=lambda: now[0])
    assert [rl.allow("a"), rl.allow("a"), rl.allow("a")] == [True, True, False]
    assert rl.allow("b") is True
    assert rl.allow("c") is False  # day cap of 3 reached
    now[0] = 3601.0
    assert rl.allow("a") is False  # still the same day


def test_voice_ws_closes_4003_without_key(client, monkeypatch):
    from starlette.websockets import WebSocketDisconnect
    monkeypatch.delenv("SARVAM_API_KEY", raising=False)
    with client.websocket_connect("/api/voice?session=t1") as ws:
        with pytest.raises(WebSocketDisconnect) as e:
            ws.receive_text()
    assert e.value.code == 4003


def test_app_start_does_not_import_pipecat():
    import subprocess
    import sys
    code = "import sys, app.main; print('pipecat' in sys.modules)"
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert out.stdout.strip() == "False"


def test_brain_lives_on_its_session_so_eviction_frees_it(keyed):
    keyed.post("/api/agent/text", json={"text": "hello"}, headers=H)
    agent = keyed.app.state.agent_sessions["agent-test-1"]
    assert agent.brain is not None and not hasattr(keyed.app.state, "text_brains")


def test_dockerfile_trusts_proxy_headers_for_rate_limits():
    """Behind Cloud Run every visitor would share one rate-limit bucket without forwarded client IPs."""
    from pathlib import Path
    cmd = Path("Dockerfile").read_text()
    assert "--proxy-headers" in cmd and "--forwarded-allow-ips" in cmd
