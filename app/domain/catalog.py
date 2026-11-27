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


def _stems(text: str) -> set[str]:
    """Words with a plural 's' dropped: 'girls pants' -> {'girl', 'pant'}."""
    return {w[:-1] if len(w) > 3 and w.endswith("s") else w for w in normalise(text).split()}


# Words that name who an item is for. If what was said has one the item's own name lacks, it is a different item.
AUDIENCE = {"women", "woman", "ladie", "lady", "teen", "teenage", "boy", "men", "man", "girl", "kid", "baby",
            "gent"}


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

    def closest(self, spoken: str, n: int = 3) -> list[Item]:
        """Up to n items whose names sound close to what was said, for 'did you mean' suggestions."""
        found: list[Item] = []
        for name in difflib.get_close_matches(normalise(spoken), list(self._names), n=n * 4, cutoff=0.5):
            item = self._items[self._names[name]]
            if item not in found:
                found.append(item)
        return found[:n]

    def plausible(self, item: Item, spoken: str) -> bool:
        """Does what was said fit this item? Guards against the AI picking the code of a different item
        (27 Nov probe: "women's pant" was given the Girls pant code)."""
        said = _stems(spoken)
        own = set().union(*(_stems(n) for n in (item.name, *item.aliases)))
        if (said & AUDIENCE) - own:  # "teen girls pant" is not "Girls pant" (27 Nov real-note check)
            return False
        if self.match(spoken) == item:
            return True
        return any(_stems(n) <= said for n in (item.name, *item.aliases))

    def match(self, spoken: str) -> Item | None:
        key = normalise(spoken)
        if not key:
            return None
        code = self._names.get(key) or self._names.get(key.replace(" ", ""))
        if code is None:
            close = difflib.get_close_matches(key, list(self._names), n=1, cutoff=0.8)
            code = self._names[close[0]] if close else None
        return self._items.get(code) if code else None
