"""Make the keyless sample's synthetic voices with Sarvam Bulbul (run once, with SARVAM_API_KEY set).

The assistant's lines are taken by running the sample through the app itself, so the audio always says exactly what
the code says; tests/test_sample_api.py fails if the code and the saved audio texts ever drift apart.
Usage: python scripts/make_sample_audio.py
"""
from __future__ import annotations

import base64
import json
import os
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "app" / "sample" / "audio"
URL = "https://api.sarvam.ai/text-to-speech"


def speak(key: str, text: str, language: str, speaker: str) -> bytes:
    r = httpx.post(URL, headers={"api-subscription-key": key}, timeout=60,
                   json={"text": text, "target_language_code": language, "model": "bulbul:v3", "speaker": speaker,
                         "speech_sample_rate": 16000})
    r.raise_for_status()
    return base64.b64decode(r.json()["audios"][0])


def main() -> None:
    key = os.environ.get("SARVAM_API_KEY", "").strip()
    if not key:
        sys.exit("Set SARVAM_API_KEY first.")
    from fastapi.testclient import TestClient

    from app.main import create_app

    steps = json.loads((ROOT / "app/sample/conversation.json").read_text(encoding="utf-8"))["steps"]
    client = TestClient(create_app(db_path=":memory:"))
    headers = {"X-Sample-Session": "make-audio"}
    client.post("/api/sample/reset", headers=headers)
    bot_texts = [" ".join(client.post("/api/sample/next", headers=headers).json()["spoken"]) for _ in steps]

    OUT.mkdir(parents=True, exist_ok=True)
    for n, (step, bot_text) in enumerate(zip(steps, bot_texts), 1):
        note = step["user_text"].startswith("Forwarded voice note")
        user_lang = "hi-IN" if note else step["language"]
        user_text = step["user_text"].split(": ", 1)[1] if note else step["user_text"]
        (OUT / f"step{n}-user.wav").write_bytes(speak(key, user_text, user_lang, "anand" if note else "shubh"))
        (OUT / f"step{n}-bot.wav").write_bytes(speak(key, bot_text, step["language"], "priya"))
        print(f"step {n}: ok")
    (OUT / "say_texts.json").write_text(json.dumps({"bot": bot_texts}, ensure_ascii=False, indent=1),
                                        encoding="utf-8")


if __name__ == "__main__":
    main()
