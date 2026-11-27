import json

import httpx
import pytest

from app.providers.base import Transcript
from tests.test_audio import make_wav

H = {"X-Agent-Session": "upload-test"}
ASK = {"choices": [{"message": {"role": "assistant", "content": "Which customer is this for?"}}],
       "usage": {"prompt_tokens": 10, "completion_tokens": 5}}


class FakeSTT:
    def __init__(self):
        self.calls = 0

    def transcribe(self, wav_path):
        self.calls += 1
        return Transcript(text="girls pant 50 piece, Girnar Transport", language="hi-IN", seconds_audio=4.0)


@pytest.fixture
def keyed(client, monkeypatch):
    monkeypatch.setenv("SARVAM_API_KEY", "test-key")
    seen = []

    def llm(request):
        seen.append(json.loads(request.content))
        return httpx.Response(200, json=ASK)

    client.app.state.llm_client = httpx.Client(transport=httpx.MockTransport(llm))
    client.app.state.stt = FakeSTT()
    client.seen = seen
    return client


def upload(client, path, name="note.ogg"):
    with open(path, "rb") as f:
        return client.post("/api/agent/upload", files={"audio": (name, f, "audio/ogg")}, headers=H)


def test_upload_503_without_key(client, monkeypatch, tmp_path):
    monkeypatch.delenv("SARVAM_API_KEY", raising=False)
    assert upload(client, make_wav(tmp_path / "a.wav")).status_code == 503


def test_upload_garbage_422(keyed, tmp_path):
    bad = tmp_path / "bad.ogg"
    bad.write_bytes(b"not audio at all")
    r = upload(keyed, bad)
    assert r.status_code == 422 and r.json()["detail"] == "This file is not audio we can read"


def test_upload_runs_text_brain(keyed, tmp_path):
    r = upload(keyed, make_wav(tmp_path / "a.wav", seconds_tone=1.5))
    assert r.status_code == 200
    body = r.json()
    assert body["transcript"] == "girls pant 50 piece, Girnar Transport"
    assert body["spoken"] == ["Which customer is this for?"]
    user_msg = keyed.seen[0]["messages"][-1]
    assert user_msg == {"role": "user", "content": "Forwarded voice note from a buyer: girls pant 50 piece, "
                                                   "Girnar Transport"}


def test_transcribe_only(keyed, tmp_path):
    with open(make_wav(tmp_path / "a.wav", seconds_tone=1.5), "rb") as f:
        r = keyed.post("/api/agent/transcribe", files={"audio": ("a.wav", f, "audio/wav")}, headers=H)
    assert r.status_code == 200 and r.json() == {"transcript": "girls pant 50 piece, Girnar Transport",
                                                 "language": "hi-IN"}
    assert keyed.seen == []
