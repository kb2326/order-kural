"""The shop's item list: codes, names, spoken aliases, list rates and minimum-quantity rules."""
from __future__ import annotations

import difflib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal


@dataclass(frozen=True)
class Item:
    code: str
    name: str
    aliases: tuple[str, ...]
    category: str
    rate_paise: int
    hsn: str
    min_kind: Literal["per_size", "total", "none"]
    min_qty: int


def normalise(text: str) -> str:
    """Casefold, keep letters only, collapse spaces: 'Crop-Tops ' -> 'crop tops'."""
    return " ".join(re.sub(r"[^a-z]+", " ", text.casefold()).split())


class Catalog:
    def __init__(self, items: list[Item]):
        self._items = {i.code: i for i in items}
        self._names: dict[str, str] = {}
        for item in items:
            for spoken in (item.name, *item.aliases):
                self._names[normalise(spoken)] = item.code
                self._names[normalise(spoken).replace(" ", "")] = item.code

    @classmethod
    def load(cls, path: str | Path) -> Catalog:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls([
            Item(code=r["code"], name=r["name"], aliases=tuple(r.get("aliases", [])), category=r["category"],
                 rate_paise=int(r["rate_rupees"]) * 100, hsn=r["hsn"], min_kind=r["min_kind"],
                 min_qty=int(r["min_qty"]))
            for r in raw["items"]
        ])

    def all(self) -> list[Item]:
        return list(self._items.values())

    def get(self, code: str) -> Item | None:
        return self._items.get(code)

    def match(self, spoken: str) -> Item | None:
        key = normalise(spoken)
        if not key:
            return None
        code = self._names.get(key) or self._names.get(key.replace(" ", ""))
        if code is None:
            close = difflib.get_close_matches(key, list(self._names), n=1, cutoff=0.8)
            code = self._names[close[0]] if close else None
        return self._items.get(code) if code else None
