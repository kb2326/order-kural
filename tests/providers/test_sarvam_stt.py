import httpx
import pytest

from app.providers.base import ProviderError
from app.providers.sarvam_stt import SarvamSTT
from tests.test_audio import make_wav


def test_sarvam_stt_joins_chunks(tmp_path):
    seen = []

    def handler(request: httpx.Request):
        body = request.content
        seen.append((request.headers.get("api-subscription-key"), body))
        text = ["Girls pant 50 piece", "Girnar Transport"][len(seen) - 1]
        return httpx.Response(200, json={"transcript": text, "language_code": "hi-IN"})

    wav = make_wav(tmp_path / "note.wav", seconds_tone=2.0, seconds_silence=1.0, repeats=2)
    stt = SarvamSTT("k", client=httpx.Client(transport=httpx.MockTransport(handler)), max_len=3.5)
    t = stt.transcribe(wav)
    assert t.text == "Girls pant 50 piece Girnar Transport" and t.language == "hi-IN"
    assert 5.5 < t.seconds_audio < 6.5 and len(seen) == 2
    key, body = seen[0]
    assert key == "k" and b'name="model"' in body and b"saaras:v4" in body and b"codemix" in body
    assert b"unknown" in body


def test_sarvam_stt_5xx_raises_provider_error(tmp_path):
    wav = make_wav(tmp_path / "note.wav")
    stt = SarvamSTT("k", client=httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(503))))
    with pytest.raises(ProviderError):
        stt.transcribe(wav)
