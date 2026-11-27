"""Estimated cost of each call in paise, from list prices (RFC section 6). Always rounded up, never under-reported."""
from __future__ import annotations

import math
from fractions import Fraction

STT_PAISE_PER_MINUTE = Fraction(49)            # Rs 0.49 per minute of audio
CHAT_PAISE_PER_INPUT_TOKEN = Fraction(1000, 10**6)   # Rs 10 per 1M input tokens
CHAT_PAISE_PER_OUTPUT_TOKEN = Fraction(2500, 10**6)  # Rs 25 per 1M output tokens
TTS_PAISE_PER_CHAR = Fraction(250, 1000)       # Rs 2.5 per 1,000 characters


def _up(value: Fraction) -> int:
    return math.ceil(value)


def stt_paise(seconds: float) -> int:
    return _up(Fraction(seconds).limit_denominator(1000) / 60 * STT_PAISE_PER_MINUTE)


def chat_paise(inp: int, out: int) -> int:
    return _up(inp * CHAT_PAISE_PER_INPUT_TOKEN + out * CHAT_PAISE_PER_OUTPUT_TOKEN)


def tts_paise(chars: int) -> int:
    return _up(chars * TTS_PAISE_PER_CHAR)
