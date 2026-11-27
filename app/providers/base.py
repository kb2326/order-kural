"""The shapes every provider must fit. Code depends on these, never on a vendor directly."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


class ProviderError(Exception):
    """A provider call failed. The message is safe to show to the user."""


@dataclass
class Transcript:
    text: str
    language: str
    seconds_audio: float


class SpeechToText(Protocol):
    def transcribe(self, wav_path: Path) -> Transcript: ...


class TextToSpeech(Protocol):
    def speak(self, text: str, language: str) -> bytes: ...
