"""Tamil number words (as live speech-to-text writes them in English letters) turned into digits, in code, before
the AI sees the text. The 27 Nov eval showed the AI sometimes dropping 'irupathu naalu' (24); digits are read
reliably, and they also let the size check confirm that an age band was really said."""
from __future__ import annotations

import re

UNITS = {"onnu": 1, "ondru": 1, "rendu": 2, "randu": 2, "moonu": 3, "naalu": 4, "nalu": 4, "anju": 5, "aaru": 6,
         "ezhu": 7, "ettu": 8, "ombodhu": 9, "ombadhu": 9}
TEENS = {"pathinonnu": 11, "pannendu": 12, "panirendu": 12, "pathimoonu": 13, "pathinaalu": 14, "pathinanju": 15,
         "pathinaaru": 16, "pathinezhu": 17, "pathinettu": 18, "pathonbathu": 19}
TENS = {"pathu": 10, "padhu": 10, "irupathu": 20, "irubathu": 20, "irupaththu": 20, "muppathu": 30, "muppadhu": 30,
        "naarpathu": 40, "narpathu": 40, "aimbathu": 50, "aimpathu": 50, "ambathu": 50, "arubathu": 60,
        "ezhupathu": 70, "embathu": 80, "thonnooru": 90, "nooru": 100}
THOUSANDS = {"aayiram": 1000, "paththayiram": 10000, "pathayiram": 10000, "anjayiram": 5000, "ainthayiram": 5000,
             "rendayiram": 2000, "irandayiram": 2000}
# Joined tens+unit forms that STT produces, e.g. "irupathinaalu" (24): tens stem + optional "i" + unit.
TENS_STEMS = {"irupath": 20, "irubath": 20, "muppath": 30, "naarpath": 40, "aimbath": 50, "aimpath": 50}

_WORD = re.compile(r"[A-Za-z]+")


def _value(word: str) -> int | None:
    w = word.casefold()
    for table in (THOUSANDS, TEENS, TENS, UNITS):
        if w in table:
            return table[w]
    for stem, tens in TENS_STEMS.items():
        if w.startswith(stem):
            rest = w[len(stem):].removeprefix("i").removeprefix("u")
            if rest in UNITS:
                return tens + UNITS[rest]
    return None


def digits(text: str) -> str:
    """'irupathu naalu print palazzo' -> '24 print palazzo'; 'randu dozen' -> '24'. Other words are untouched."""
    tokens = re.split(r"(\s+)", text)
    out: list[str] = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        m = _WORD.fullmatch(tok)
        val = _value(tok) if m else None
        if val is None:
            out.append(tok)
            i += 1
            continue
        # tens followed by a unit ("irupathu naalu") -> one number
        if val in (20, 30, 40, 50, 60, 70, 80, 90) and i + 2 < len(tokens) and tokens[i + 2].casefold() in UNITS:
            val += UNITS[tokens[i + 2].casefold()]
            i += 2
        # "randu dozen" -> 24
        if i + 2 < len(tokens) and tokens[i + 2].casefold() in ("dozen", "dazan") and val < 100:
            val *= 12
            i += 2
        out.append(str(val))
        i += 1
    return "".join(out)
