"""Is this reply a yes, a no, or something else? Plain word lists, no AI, so "sari" can never be misread as a new
order and the AI cannot confirm on its own."""
from __future__ import annotations

import re
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


# Phrases where the AI says it did something (added / saved / put / set) in Tamil, Hindi, English and Malayalam.
CLAIM = re.compile(r"\b(add|added|adding|save|saved|saving|billed)\b|panren|panniten|panniduren|pannuren|potten|"
                   r"podaren|seththuten|serthuten|சேர்த்து|சேர்த்தேன்|போட்டேன்|जोड़|जोड़|सेव कर|ചേർത്ത",
                   re.IGNORECASE)


def unbacked_claim(text: str, tool_called: bool, item_names: tuple[str, ...] = ()) -> bool:
    """True when the AI's own words claim an action, or read out order items, but no tool ran in that turn
    (27 Nov: it said 'girls pant ... add panren', and once echoed 'crop top S aaru M aaru', saving nothing).
    A question ('crop top M size-la ethana?') is not a claim. The caller then says, in code, that nothing was added."""
    if tool_called or not text:
        return False
    if CLAIM.search(text):
        return True
    lowered = text.casefold()
    return "?" not in text and any(name in lowered for name in item_names)


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
