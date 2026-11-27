import pytest

from app.obs.trace import span
from app.providers import costs
from app.store.db import Store


def test_span_records_time_and_cost():
    store = Store(":memory:")
    with span(store, 7, "stt", "sarvam") as s:
        s["cost_paise"] = 3
        s["meta"] = {"seconds_audio": 12.5}
    rows = store.traces_for(7)
    assert len(rows) == 1
    row = rows[0]
    assert row["span"] == "stt" and row["provider"] == "sarvam"
    assert row["ok"] == 1 and row["error"] is None
    assert row["cost_paise"] == 3 and row["ms"] >= 0
    assert row["meta"] == {"seconds_audio": 12.5}


def test_span_records_error_and_reraises():
    store = Store(":memory:")
    with pytest.raises(RuntimeError, match="boom"):
        with span(store, None, "chat", "sarvam"):
            raise RuntimeError("boom")
    row = store.recent_traces(1)[0]
    assert row["ok"] == 0 and row["error"] == "boom" and row["piece_id"] is None


def test_costs_round_up():
    assert costs.stt_paise(60) == 49
    assert costs.chat_paise(429, 531) == 2
    assert costs.tts_paise(1000) == 250
    assert costs.stt_paise(0) == 0
