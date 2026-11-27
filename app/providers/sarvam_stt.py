"""Sarvam speech-to-text for uploaded notes (batch REST API, at most 30 s per request, so long notes are cut at
pauses first). Verified 27 Nov: saaras:v4, codemix, language auto-detect."""
from __future__ import annotations

import tempfile
from pathlib import Path

import httpx

from app.audio import choose_cuts, silences, split
from app.audio import _seconds as wav_seconds
from app.providers.base import ProviderError, Transcript

URL = "https://api.sarvam.ai/speech-to-text"


class SarvamSTT:
    def __init__(self, api_key: str, client: httpx.Client | None = None, max_len: float = 28.0):
        self.api_key = api_key
        self.client = client or httpx.Client(timeout=60)
        self.max_len = max_len

    def _one(self, wav: Path) -> dict:
        try:
            with wav.open("rb") as f:
                r = self.client.post(URL, headers={"api-subscription-key": self.api_key},
                                     files={"file": (wav.name, f, "audio/wav")},
                                     data={"model": "saaras:v4", "mode": "codemix", "language_code": "unknown"})
            r.raise_for_status()
            return r.json()
        except (httpx.HTTPError, ValueError) as e:
            raise ProviderError("Speech-to-text failed. Please try again, or type it.") from e

    def transcribe(self, wav_path: Path) -> Transcript:
        seconds = wav_seconds(wav_path)
        cuts = choose_cuts(seconds, silences(wav_path), self.max_len)
        with tempfile.TemporaryDirectory() as tmp:
            parts = split(wav_path, cuts, Path(tmp)) if cuts else [wav_path]
            results = [self._one(p) for p in parts]
        texts = [(r.get("transcript") or "").strip() for r in results]
        language = next((r.get("language_code") for r, t in zip(results, texts) if t), None) or "unknown"
        return Transcript(text=" ".join(t for t in texts if t), language=language, seconds_audio=seconds)
