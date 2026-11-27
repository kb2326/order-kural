"""Is this reply a yes, a no, or something else? Plain word lists, no AI, so "sari" can never be misread as a new
order and the AI cannot confirm on its own."""
from __future__ import annotations

from typing import Literal

YES = {"sari", "seri", "saari", "aamaa", "aama", "haan", "ha", "theek hai", "ok", "okay", "confirm", "correct",
       "howdu", "houdu", "sheri", "athe", "சரி", "ஆமா", "हाँ", "हां", "ठीक है", "ശരി", "ಹೌದು", "ಸರಿ"}
NO = {"vendaam", "vendam", "venda", "cancel", "nahi", "nahin", "no", "beda", "വേണ്ട", "ಬೇಡ", "வேண்டாம்", "नहीं"}
PUNCT = set(".,!?;:'\"()[]{}-–—…।|")
MAX_YES_WORDS = 3


def _tokens(text: str) -> list[str]:
    cleaned = "".join(" " if ch in PUNCT else ch for ch in text.casefold())
    return cleaned.split()


def _has(tokens: list[str], words: set[str]) -> bool:
    joined = f" {' '.join(tokens)} "
    return any(f" {w} " in joined for w in words)


def classify(text: str) -> Literal["yes", "no", "other"]:
    tokens = _tokens(text)
    yes, no = _has(tokens, YES), _has(tokens, NO)
    if yes and no:
        return "other"
    if no:
        return "no"
    if yes and len(tokens) <= MAX_YES_WORDS:
        return "yes"
    return "other"
