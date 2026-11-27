"""SQLite store. Tables follow Tally's record chain (RFC section 5): customer -> order -> lines, with every voice
piece and every applied change kept, so each line can be traced back to the voice note it came from."""
from __future__ import annotations

import json
import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Literal

from app.domain.order import Order, OrderLine

SCHEMA = """
CREATE TABLE IF NOT EXISTS customers (
    id INTEGER PRIMARY KEY, name TEXT NOT NULL, city TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY, customer_id INTEGER NOT NULL REFERENCES customers(id),
    state TEXT NOT NULL DEFAULT 'open', transport TEXT, payment TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP, updated_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS order_lines (
    id INTEGER PRIMARY KEY, order_id INTEGER NOT NULL REFERENCES orders(id), position INTEGER NOT NULL,
    item_code TEXT NOT NULL, sizes_json TEXT NOT NULL, quantity INTEGER NOT NULL, rate_paise INTEGER NOT NULL,
    flags_json TEXT NOT NULL, source_piece_id INTEGER REFERENCES voice_pieces(id));
CREATE TABLE IF NOT EXISTS voice_pieces (
    id INTEGER PRIMARY KEY, source TEXT NOT NULL, transcript TEXT NOT NULL, audio_path TEXT,
    state TEXT NOT NULL DEFAULT 'transcribed', ai_result_json TEXT, proposal_json TEXT,
    target_order_id INTEGER, order_id INTEGER, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS order_events (
    id INTEGER PRIMARY KEY, order_id INTEGER NOT NULL, piece_id INTEGER NOT NULL, change_json TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS traces (
    id INTEGER PRIMARY KEY, piece_id INTEGER, span TEXT NOT NULL, ms INTEGER, cost_paise INTEGER,
    meta_json TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
"""


class Store:
    def __init__(self, db_path: str):
        if db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        # One connection is shared by FastAPI's worker threads, so every access goes through this lock.
        self.lock = threading.RLock()
        self._depth = 0

    @contextmanager
    def tx(self) -> Iterator[None]:
        """One transaction. Nested calls join the outer one, so a whole confirm commits or rolls back together."""
        with self.lock:
            if self._depth:
                self._depth += 1
                try:
                    yield
                finally:
                    self._depth -= 1
                return
            self._depth = 1
            try:
                with self.conn:
                    yield
            finally:
                self._depth = 0

    # ---- orders -------------------------------------------------------------------------------------------
    def _load_order(self, row: sqlite3.Row) -> Order:
        lines = [
            OrderLine(item_code=l["item_code"], sizes=json.loads(l["sizes_json"]), quantity=l["quantity"],
                      rate_paise=l["rate_paise"], flags=json.loads(l["flags_json"]),
                      source_piece_id=l["source_piece_id"])
            for l in self.conn.execute("SELECT * FROM order_lines WHERE order_id=? ORDER BY position", (row["id"],))
        ]
        return Order(id=row["id"], customer_name=row["name"], city=row["city"], state=row["state"],
                     transport=row["transport"], payment=row["payment"], lines=lines)

    _ORDER_SQL = ("SELECT o.id, o.state, o.transport, o.payment, c.name, c.city "
                  "FROM orders o JOIN customers c ON c.id = o.customer_id")

    def open_orders(self) -> list[Order]:
        with self.lock:
            return self._open_orders()

    def _open_orders(self) -> list[Order]:
        rows = self.conn.execute(self._ORDER_SQL + " WHERE o.state='open' ORDER BY o.id").fetchall()
        return [self._load_order(r) for r in rows]

    def get_order(self, order_id: int) -> Order | None:
        with self.lock:
            row = self.conn.execute(self._ORDER_SQL + " WHERE o.id=?", (order_id,)).fetchone()
            return self._load_order(row) if row else None

    def _customer_id(self, name: str, city: str | None) -> int:
        row = self.conn.execute(
            "SELECT id, city FROM customers WHERE lower(name)=lower(?) AND (city IS ? OR lower(city)=lower(?) "
            "OR city IS NULL OR ? IS NULL) ORDER BY id LIMIT 1", (name, city, city, city)).fetchone()
        if row:
            if city and not row["city"]:
                self.conn.execute("UPDATE customers SET city=? WHERE id=?", (city, row["id"]))
            return row["id"]
        return self.conn.execute("INSERT INTO customers(name, city) VALUES (?, ?)", (name, city)).lastrowid

    def save_order(self, order: Order) -> int:
        with self.tx():
            cid = self._customer_id(order.customer_name, order.city)
            if order.id is None:
                order_id = self.conn.execute(
                    "INSERT INTO orders(customer_id, state, transport, payment) VALUES (?, ?, ?, ?)",
                    (cid, order.state, order.transport, order.payment)).lastrowid
            else:
                order_id = order.id
                self.conn.execute(
                    "UPDATE orders SET customer_id=?, state=?, transport=?, payment=?, updated_at=CURRENT_TIMESTAMP "
                    "WHERE id=?", (cid, order.state, order.transport, order.payment, order_id))
                self.conn.execute("DELETE FROM order_lines WHERE order_id=?", (order_id,))
            self.conn.executemany(
                "INSERT INTO order_lines(order_id, position, item_code, sizes_json, quantity, rate_paise, "
                "flags_json, source_piece_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                [(order_id, i, l.item_code, json.dumps(l.sizes), l.quantity, l.rate_paise, json.dumps(l.flags),
                  l.source_piece_id) for i, l in enumerate(order.lines)])
        return order_id

    # ---- voice pieces -------------------------------------------------------------------------------------
    def add_piece(self, transcript: str, source: Literal["live", "sample"], audio_path: str | None) -> int:
        with self.tx():
            return self.conn.execute("INSERT INTO voice_pieces(source, transcript, audio_path) VALUES (?, ?, ?)",
                                     (source, transcript, audio_path)).lastrowid

    def get_piece(self, piece_id: int) -> dict | None:
        with self.lock:
            row = self.conn.execute("SELECT * FROM voice_pieces WHERE id=?", (piece_id,)).fetchone()
            return dict(row) if row else None

    _PIECE_FIELDS = {"state", "ai_result_json", "proposal_json", "target_order_id", "order_id", "transcript"}

    def claim_piece(self, piece_id: int, from_state: str, to_state: str) -> bool:
        """Move a piece between states only if it is still in from_state. False means someone else got there first."""
        with self.tx():
            cur = self.conn.execute("UPDATE voice_pieces SET state=? WHERE id=? AND state=?",
                                    (to_state, piece_id, from_state))
            return cur.rowcount == 1

    def update_piece(self, piece_id: int, **fields) -> None:
        bad = set(fields) - self._PIECE_FIELDS
        if bad:
            raise ValueError(f"Unknown piece fields: {sorted(bad)}")
        sets = ", ".join(f"{k}=?" for k in fields)
        with self.tx():
            self.conn.execute(f"UPDATE voice_pieces SET {sets} WHERE id=?", (*fields.values(), piece_id))

    def count_pieces(self, source: str) -> int:
        with self.lock:
            return self.conn.execute("SELECT COUNT(*) FROM voice_pieces WHERE source=?", (source,)).fetchone()[0]

    def add_event(self, order_id: int, piece_id: int, change_json: str) -> None:
        with self.tx():
            self.conn.execute("INSERT INTO order_events(order_id, piece_id, change_json) VALUES (?, ?, ?)",
                              (order_id, piece_id, change_json))

    def reset(self) -> None:
        with self.tx():
            for table in ("order_events", "order_lines", "orders", "customers", "voice_pieces", "traces"):
                self.conn.execute(f"DELETE FROM {table}")
