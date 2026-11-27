"""One span per outside call: how long it took, what it cost, and whether it failed."""
from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager

from app.store.db import Store


@contextmanager
def span(store: Store, piece_id: int | None, name: str, provider: str) -> Iterator[dict]:
    """Yields a dict where the caller may set 'cost_paise' and 'meta'. Errors are recorded, then re-raised."""
    info: dict = {"cost_paise": 0, "meta": {}}
    start = time.perf_counter()
    error: str | None = None
    try:
        yield info
    except Exception as e:
        error = str(e) or type(e).__name__
        raise
    finally:
        ms = int((time.perf_counter() - start) * 1000)
        store.add_trace(piece_id=piece_id, span=name, provider=provider, ms=ms, cost_paise=info["cost_paise"],
                        ok=error is None, error=error, meta=info["meta"])
