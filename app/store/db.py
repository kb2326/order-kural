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
    state TEXT NOT NULL DEFAULT 'open', transport TEXT, payment TEXT, gstin TEXT, state_code TEXT,
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
CREATE TABLE IF NOT EXISTS bills (
    id INTEGER PRIMARY KEY, number INTEGER NOT NULL UNIQUE, order_id INTEGER NOT NULL REFERENCES orders(id),
    customer_id INTEGER NOT NULL REFERENCES customers(id), total_paise INTEGER NOT NULL, lines_json TEXT NOT NULL,
    voided INTEGER NOT NULL DEFAULT 0, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS ledger_entries (
    id INTEGER PRIMARY KEY, customer_id INTEGER NOT NULL REFERENCES customers(id),
    kind TEXT NOT NULL CHECK (kind IN ('bill', 'payment', 'reversal')), amount_paise INTEGER NOT NULL,
    ref_bill INTEGER, mode TEXT, reverses INTEGER REFERENCES ledger_entries(id),
    created_at TEXT DEFAULT CURRENT_TIMESTAMP);
CREATE TABLE IF NOT EXISTS traces (
    id INTEGER PRIMARY KEY, piece_id INTEGER, span TEXT NOT NULL, provider TEXT, ms INTEGER, cost_paise INTEGER,
    ok INTEGER NOT NULL DEFAULT 1, error TEXT, meta_json TEXT, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
"""


class Store:
    def __init__(self, db_path: str):
        if db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._upgrade_old_traces()
        self._add_missing_columns()
        self.conn.executescript(SCHEMA)
        # One connection is shared by FastAPI's worker threads, so every access goes through this lock.
        self.lock = threading.RLock()
        self._depth = 0

    def _upgrade_old_traces(self) -> None:
        """S0-S1 databases have a traces table without provider/ok/error. Nothing ever wrote to it, so recreate it."""
        cols = {r[1] for r in self.conn.execute("PRAGMA table_info(traces)")}
        if cols and "provider" not in cols:
            self.conn.execute("DROP TABLE traces")

    def _add_missing_columns(self) -> None:
        """Databases made before 27 Nov have no buyer GSTIN / place of supply on orders."""
        cols = {r[1] for r in self.conn.execute("PRAGMA table_info(orders)")}
        for col in ("gstin", "state_code"):
            if cols and col not in cols:
                self.conn.execute(f"ALTER TABLE orders ADD COLUMN {col} TEXT")

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
                     transport=row["transport"], payment=row["payment"], lines=lines, gstin=row["gstin"],
                     state_code=row["state_code"])

    _ORDER_SQL = ("SELECT o.id, o.state, o.transport, o.payment, o.gstin, o.state_code, c.name, c.city "
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
                    "INSERT INTO orders(customer_id, state, transport, payment, gstin, state_code) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (cid, order.state, order.transport, order.payment, order.gstin, order.state_code)).lastrowid
            else:
                order_id = order.id
                self.conn.execute(
                    "UPDATE orders SET customer_id=?, state=?, transport=?, payment=?, gstin=?, state_code=?, "
                    "updated_at=CURRENT_TIMESTAMP WHERE id=?",
                    (cid, order.state, order.transport, order.payment, order.gstin, order.state_code, order_id))
                self.conn.execute("DELETE FROM order_lines WHERE order_id=?", (order_id,))
            self.conn.executemany(
                "INSERT INTO order_lines(order_id, position, item_code, sizes_json, quantity, rate_paise, "
                "flags_json, source_piece_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                [(order_id, i, l.item_code, json.dumps(l.sizes), l.quantity, l.rate_paise, json.dumps(l.flags),
                  l.source_piece_id) for i, l in enumerate(order.lines)])
        return order_id

    def orders_in_states(self, states: list[str]) -> list[Order]:
        marks = ",".join("?" * len(states))
        with self.lock:
            rows = self.conn.execute(self._ORDER_SQL + f" WHERE o.state IN ({marks}) ORDER BY o.id", states).fetchall()
            return [self._load_order(r) for r in rows]

    def order_dates(self) -> dict[int, str]:
        with self.lock:
            return {r[0]: r[1] for r in self.conn.execute("SELECT id, created_at FROM orders")}

    def set_order_state(self, order_id: int, state: str) -> None:
        with self.tx():
            self.conn.execute("UPDATE orders SET state=?, updated_at=CURRENT_TIMESTAMP WHERE id=?", (state, order_id))

    def customer_id_of_order(self, order_id: int) -> int:
        with self.lock:
            return self.conn.execute("SELECT customer_id FROM orders WHERE id=?", (order_id,)).fetchone()[0]

    # ---- bills --------------------------------------------------------------------------------------------
    def next_bill_number(self) -> int:
        with self.lock:
            return self.conn.execute("SELECT COALESCE(MAX(number), 0) + 1 FROM bills").fetchone()[0]

    def save_bill(self, *, number: int, order_id: int, customer_id: int, total_paise: int, lines_json: str) -> int:
        with self.tx():
            return self.conn.execute(
                "INSERT INTO bills(number, order_id, customer_id, total_paise, lines_json) VALUES (?, ?, ?, ?, ?)",
                (number, order_id, customer_id, total_paise, lines_json)).lastrowid

    def get_bill(self, number: int) -> dict | None:
        with self.lock:
            row = self.conn.execute("SELECT * FROM bills WHERE number=?", (number,)).fetchone()
        return dict(row) if row else None

    def recent_bills(self, limit: int = 50) -> list[dict]:
        with self.lock:
            rows = self.conn.execute(
                "SELECT b.number, b.total_paise, b.voided, b.created_at, c.name AS customer FROM bills b "
                "JOIN customers c ON c.id = b.customer_id ORDER BY b.number DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]

    def all_bills(self) -> list[dict]:
        with self.lock:
            return [dict(r) for r in self.conn.execute("SELECT * FROM bills ORDER BY number")]

    def set_bill_voided(self, number: int) -> None:
        with self.tx():
            self.conn.execute("UPDATE bills SET voided=1 WHERE number=?", (number,))

    # ---- queries for 'ask the shop' ----------------------------------------------------------------------
    def bill_for_order(self, order_id: int) -> dict | None:
        with self.lock:
            row = self.conn.execute("SELECT * FROM bills WHERE order_id=? AND voided=0 ORDER BY id DESC LIMIT 1",
                                    (order_id,)).fetchone()
        return dict(row) if row else None

    def open_order_for_customer(self, customer_id: int) -> Order | None:
        with self.lock:
            row = self.conn.execute(self._ORDER_SQL + " WHERE o.state='open' AND o.customer_id=? ORDER BY o.id DESC "
                                    "LIMIT 1", (customer_id,)).fetchone()
            return self._load_order(row) if row else None

    def customer_name(self, customer_id: int) -> str:
        with self.lock:
            return self.conn.execute("SELECT name FROM customers WHERE id=?", (customer_id,)).fetchone()[0]

    def find_customers(self, name: str) -> list[dict]:
        with self.lock:
            rows = self.conn.execute("SELECT id, name, city FROM customers ORDER BY id").fetchall()
        return [dict(r) for r in rows if r["name"].casefold() == name.strip().casefold()]

    def all_customers(self) -> list[dict]:
        with self.lock:
            return [dict(r) for r in self.conn.execute("SELECT id, name, city FROM customers ORDER BY name")]

    def item_quantity_since(self, item_code: str, since: str) -> int:
        with self.lock:
            return self.conn.execute(
                "SELECT COALESCE(SUM(l.quantity), 0) FROM order_lines l JOIN orders o ON o.id = l.order_id "
                "WHERE l.item_code=? AND o.state != 'cancelled' AND o.created_at >= ?",
                (item_code, since)).fetchone()[0]

    # ---- khata -------------------------------------------------------------------------------------------
    def add_ledger(self, *, customer_id: int, kind: str, amount_paise: int, ref_bill: int | None = None,
                   mode: str | None = None, reverses: int | None = None) -> int:
        with self.tx():
            return self.conn.execute(
                "INSERT INTO ledger_entries(customer_id, kind, amount_paise, ref_bill, mode, reverses) "
                "VALUES (?, ?, ?, ?, ?, ?)", (customer_id, kind, amount_paise, ref_bill, mode, reverses)).lastrowid

    def ledger_for(self, customer_id: int) -> list[dict]:
        with self.lock:
            rows = self.conn.execute("SELECT * FROM ledger_entries WHERE customer_id=? ORDER BY id",
                                     (customer_id,)).fetchall()
        return [dict(r) for r in rows]

    def set_order_transport(self, order_id: int, transport: str) -> None:
        with self.tx():
            self.conn.execute("UPDATE orders SET transport=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                              (transport, order_id))

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

    # ---- traces -------------------------------------------------------------------------------------------

    def add_trace(self, *, piece_id: int | None, span: str, provider: str, ms: int, cost_paise: int, ok: bool,
                  error: str | None, meta: dict) -> None:
        with self.tx():
            self.conn.execute(
                "INSERT INTO traces(piece_id, span, provider, ms, cost_paise, ok, error, meta_json) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (piece_id, span, provider, ms, cost_paise, int(ok), error, json.dumps(meta, ensure_ascii=False)))

    @staticmethod
    def _trace_row(r: sqlite3.Row) -> dict:
        row = dict(r)
        row["meta"] = json.loads(row.pop("meta_json") or "{}")
        return row

    def traces_for(self, piece_id: int) -> list[dict]:
        with self.lock:
            rows = self.conn.execute("SELECT * FROM traces WHERE piece_id=? ORDER BY id", (piece_id,)).fetchall()
        return [self._trace_row(r) for r in rows]

    def recent_traces(self, limit: int = 50) -> list[dict]:
        with self.lock:
            rows = self.conn.execute("SELECT * FROM traces ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [self._trace_row(r) for r in rows]

    def reset(self) -> None:
        with self.tx():
            for table in ("order_events", "order_lines", "ledger_entries", "bills", "orders", "customers", "voice_pieces", "traces"):
                self.conn.execute(f"DELETE FROM {table}")
