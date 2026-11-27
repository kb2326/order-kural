# S0 + S1: Skeleton and Order Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A public, Docker-started Order Kural app that opens with no keys, shows a "key not set" banner, and runs a
3-piece sample conversation through the real order engine (pieces merge into one customer's order with exact totals),
confirmed by tap.

**Architecture:** One FastAPI service serving a plain HTML/JS page. Pure-Python domain code (catalogue, change models,
order engine with rules and GST in paise) with no network. A SQLite store and a piece service implement the piece
state machine (proposed → read back → applied / discarded). The sample conversation feeds saved AI results (fixtures)
into the same service the live AI will use in S3.

**Tech Stack:** Python 3.12 (Docker) / 3.13 (local), FastAPI 0.115.6, uvicorn 0.32.1, Pydantic 2.10.3, pytest 8.3.4,
httpx 0.28.1, SQLite (stdlib), Docker Compose, GitHub Actions.

**Spec:** `docs/round2/04-rfc.md` (§1 compliance, §2 architecture, §3 state machines, §4.3-4.4, §4.8, §5, §12
slices S0-S1) and `docs/round2/03-prd.md` (R4, R7, R8, R11 data link, R12, R13).

## Global Constraints

- The app **must start and show its main screen with no environment variables at all**; keys are read only when a
  feature is used.
- Banner text (exact): `Sarvam API key not set: live voice is off. Try the sample conversation to see the full flow with saved AI results.`
- Sample label (exact): `Sample: saved AI results`
- Money is **integer paise** everywhere; never floats.
- GST per line: **5%** if the per-piece rate ≤ ₹2,500 (250000 paise), else **18%**; round half up to the paise.
- Rate flag: a spoken rate more than **10%** away from the list rate is flagged `rate_off_list`.
- Minimum rules: kids' wear **10 per size**; crop tops **6 per size**; pants and palazzos **24 total**; shorts
  **10 total**.
- Nothing changes an order without `confirm` on a piece in state `read_back`.
- Port **8000**; DB path from env `ORDER_KURAL_DB`, default `data/runtime/orderkural.db`.
- Python package root: `app/`. Tests in `tests/`. Run tests with `python -m pytest -q`.
- Commits end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`; use `git commit -F <file>` (PowerShell
  breaks quoted messages).

## Review Focus

1. **The same item added twice** (piece 1 adds crop tops, piece 2 adds more) must merge into one line, not two rows.
2. **An unknown item name** must be reported as a problem in the proposal and never silently dropped or guessed.
3. **Confirming the same piece twice, or confirming a discarded piece** must return HTTP 409 and apply nothing.
4. **A piece naming a customer whose order is not open** must start a new order, not change the old one.
5. **Negative quantities** in AI output must fail validation; a size set to 0 removes that size.

---

### Task 1: App skeleton, config and status (no keys)

**Files:**
- Create: `app/__init__.py`, `app/config.py`, `app/main.py`, `app/static/index.html`, `app/static/app.js`,
  `app/static/styles.css`, `requirements.txt`, `requirements-dev.txt`, `.env.example`, `tests/__init__.py`,
  `tests/test_app_starts.py`

**Interfaces:**
- Produces: `app.config.provider_status() -> dict[str, str]` returning `{"stt": "ready"|"not_set", "llm": ..., "tts": ...}`
  (all three depend on env `SARVAM_API_KEY`, read at call time); `app.main.create_app(db_path: str | None = None) -> FastAPI`;
  module-level `app = create_app()`.

- [ ] **Step 1: Write the failing tests** in `tests/test_app_starts.py`:

```python
def test_health(client):            # client = TestClient(create_app(db_path=tmp)) via fixture
    assert client.get("/health").json() == {"ok": True}

def test_status_not_set_without_keys(client, monkeypatch):
    monkeypatch.delenv("SARVAM_API_KEY", raising=False)
    assert client.get("/api/status").json()["providers"] == {"stt": "not_set", "llm": "not_set", "tts": "not_set"}

def test_status_ready_with_key(client, monkeypatch):
    monkeypatch.setenv("SARVAM_API_KEY", "x")
    assert client.get("/api/status").json()["providers"]["stt"] == "ready"

def test_main_screen_has_banner_text(client):
    html = client.get("/").text
    assert "Order Kural" in html
    assert "Sarvam API key not set: live voice is off." in html
```

Put the `client` fixture in `tests/conftest.py` using `tmp_path / "t.db"`.

- [ ] **Step 2: Run** `python -m pytest -q tests/test_app_starts.py` → FAIL (no module `app`).
- [ ] **Step 3: Implement.** `create_app` mounts `app/static` at `/static`, serves `index.html` at `/`, adds `/health`
  and `/api/status` (`{"providers": provider_status(), "sample_available": true}`). `index.html` contains the header,
  the banner element (`id="key-banner"`, exact banner text, `hidden`), a disabled mic button with label
  `Hold to talk (key not set)`, the sample button `Try the sample conversation`, and empty containers `#proposal`,
  `#orders`. `app.js` fetches `/api/status` and un-hides the banner when any provider is `not_set`.
  `requirements.txt`: `fastapi==0.115.6`, `uvicorn[standard]==0.32.1`, `pydantic==2.10.3`.
  `requirements-dev.txt`: `-r requirements.txt`, `pytest==8.3.4`, `httpx==0.28.1`. `.env.example`: `SARVAM_API_KEY=`.
- [ ] **Step 4: Run** the tests → PASS. Also `python -m uvicorn app.main:app --port 8000` and open
  `http://localhost:8000` → banner visible.
- [ ] **Step 5: Commit** `feat: app skeleton with no-key status banner`.

### Task 2: Docker, Compose, CI and README run section

**Files:**
- Create: `Dockerfile`, `docker-compose.yml`, `.dockerignore`, `.github/workflows/ci.yml`, `README.md`

**Interfaces:**
- Consumes: `app.main:app` (Task 1).

- [ ] **Step 1: Write** `Dockerfile`: `python:3.12-slim`; `apt-get install -y --no-install-recommends ffmpeg`
  (needed from S2); install `requirements.txt`; copy `app/` and `data/`; `CMD uvicorn app.main:app --host 0.0.0.0
  --port 8000`. `docker-compose.yml`: one service `app`, `build: .`, `ports: ["8000:8000"]`,
  `env_file: [{path: .env, required: false}]`, named volume `orderkural-data` at `/app/data/runtime`,
  `healthcheck` hitting `/health`. `.dockerignore`: `.env`, `.git`, `.venv`, `data/private`, `data/runtime`, `docs`.
- [ ] **Step 2: Write** `.github/workflows/ci.yml` with two jobs: `test` (Python 3.12, `pip install -r
  requirements-dev.txt`, `python -m pytest -q`) and `docker` (`docker compose up -d --build` with **no** `.env`;
  wait for health; `curl -fsS localhost:8000/health`; `curl -fsS localhost:8000/api/status | grep not_set`;
  `curl -fsS localhost:8000/ | grep "Sarvam API key not set"`; `docker compose down`).
- [ ] **Step 3: Write** `README.md` (owner's request: clean, easy to understand, with Mermaid diagrams that render on
  GitHub). Sections in this order:
  1. Title + one-line pitch: "The shop's ledger that listens. Listens like ChatGPT, remembers like Tally."
  2. **The problem** (3 short lines: the order lives everywhere; written 3 times; nothing remembers).
  3. **What it does** (5 bullets: speak any piece · AI finds the customer and the change · code does the maths ·
     read back, say "sari" · bill, khata, to-ship).
  4. **Run it in one command** (`git clone`, `cd order-kural`, `docker compose up --build`, open
     `http://localhost:8000`) + "Works without keys: try the sample conversation" + "Live voice: copy `.env.example`
     to `.env` and set `SARVAM_API_KEY`".
  5. **How an order is built** — Mermaid `sequenceDiagram`: Owner → App (voice piece) → Sarvam STT → AI (customer +
     changes) → Rules engine (prices, minimums, GST) → App reads back → Owner says "sari" → Order updated; repeated for
     piece 2 and 3; then "bill it".
  6. **Architecture** — Mermaid `flowchart LR`: Browser → FastAPI (api, flow, domain, providers, store) → Sarvam
     (STT, sarvam-105b, Bulbul) and SQLite.
  7. **Order life cycle** — Mermaid `stateDiagram-v2` for the voice piece (received → transcribed → proposed →
     read_back → applied/discarded) and the order (open → billed → shipped; open → cancelled).
  8. **Why AI and why code** (table: AI reads, code calculates, human confirms).
  9. **Project docs** (links: story, life cycle, PRD, RFC, ADRs, eval set).
  10. **Built by voice** with Wispr Flow (one line + link to `docs/round2/built-by-voice.md`).
  Keep sentences short; no jargon without a one-line explanation. Add a "Status" line listing which slices work.
- [ ] **Step 4: Verify** (needs Docker Desktop running): `docker compose up -d --build`; `curl.exe -fsS
  http://localhost:8000/health` → `{"ok":true}`; `docker compose down`. Push and check the Actions run is green:
  `gh run list --limit 1`.
- [ ] **Step 5: Commit** `build: docker compose, CI no-key start check, README`.

### Task 3: Catalogue and money helpers

**Files:**
- Create: `data/items.json`, `app/domain/__init__.py`, `app/domain/money.py`, `app/domain/catalog.py`,
  `tests/domain/__init__.py`, `tests/domain/test_catalog.py`

**Interfaces:**
- Produces: `Item` (frozen dataclass: `code: str, name: str, aliases: tuple[str, ...], category: str, rate_paise: int,
  hsn: str, min_kind: Literal["per_size","total","none"], min_qty: int`); `Catalog` with
  `Catalog.load(path: str | Path) -> Catalog`, `.get(code: str) -> Item | None`, `.match(spoken: str) -> Item | None`,
  `.all() -> list[Item]`; `money.format_inr(paise: int) -> str` (e.g. `832860 → "₹8,328.60"`, Indian grouping
  `12345678 → "₹1,23,456.78"`).

Seed `data/items.json` with these 13 items (rates from the real notebook; crop top ₹75 is an estimate, mark
`"rate_note": "estimate"`):

| code | name | aliases | category | rate ₹ | hsn | min |
|---|---|---|---|---|---|---|
| BTS | Boys T-shirt | boys tshirt | kids | 55 | 6109 | per_size 10 |
| GTS | Girls T-shirt | girls tshirt | kids | 55 | 6109 | per_size 10 |
| TSH | T-shirt S-M-L | tshirt, t shirt | tshirt | 60 | 6109 | none 0 |
| SHS | Shorts set | shorts | shorts | 85 | 6104 | total 10 |
| PNS | Pant set | pant set | pants | 95 | 6104 | total 24 |
| STP | Stone pant | stone pants | pants | 45 | 6104 | total 24 |
| PPL | Plain palazzo | plain palazzo pant | palazzo | 65 | 6104 | total 24 |
| PRP | Print palazzo | printed palazzo, print palazzo pant | palazzo | 68 | 6104 | total 24 |
| KPT | Kids pant | kids pants | kids | 28 | 6104 | per_size 10 |
| PCS | Popcorn pant set | popcorn set | pants | 95 | 6104 | total 24 |
| GPT | Girls pant | girls pants | kids | 55 | 6104 | per_size 10 |
| KPS | Kids palazzo set | kids palazzo | kids | 120 | 6104 | per_size 10 |
| CRT | Crop top | croptop, crop tops | crop | 75 | 6109 | per_size 6 |

- [ ] **Step 1: Write failing tests:** `test_load_has_13_items`; `test_get_by_code` (`get("PRP").rate_paise == 6800`);
  `test_match_exact_alias_and_case` (`match("PRINT PALAZZO").code == "PRP"`, `match("croptop").code == "CRT"`);
  `test_match_near_spelling` (`match("print palazo").code == "PRP"`); `test_match_unknown_returns_none`
  (`match("saree") is None`); `test_format_inr` (`format_inr(832860) == "₹8,328.60"`,
  `format_inr(12345678) == "₹1,23,456.78"`, `format_inr(0) == "₹0.00"`).
- [ ] **Step 2: Run** `python -m pytest -q tests/domain/test_catalog.py` → FAIL.
- [ ] **Step 3: Implement.** `match` normalises (casefold, strip non-letters, collapse spaces), tries exact name or
  alias, then `difflib.get_close_matches` over names + aliases with `cutoff=0.8`.
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat: seeded catalogue with item codes and INR formatting`.

### Task 4: Change models (the AI's output contract)

**Files:**
- Create: `app/domain/changes.py`, `tests/domain/test_changes.py`

**Interfaces:**
- Produces (Pydantic v2): `AddLine(op: Literal["add_line"], item_code: str | None, name_as_spoken: str,
  sizes: dict[str, NonNegativeInt] = {}, quantity_total: NonNegativeInt | None = None, rate_spoken: PositiveInt | None = None)`
  (rate in whole rupees); `ChangeLine(op: Literal["change_line"], item_code: str, sizes: dict[str, NonNegativeInt] | None = None,
  quantity_total: NonNegativeInt | None = None, rate_spoken: PositiveInt | None = None)`;
  `RemoveLine(op: Literal["remove_line"], item_code: str)`;
  `SetField(op: Literal["set_field"], field: Literal["transport","payment","city"], value: str)`;
  `Change = Annotated[AddLine | ChangeLine | RemoveLine | SetField, Field(discriminator="op")]`;
  `CustomerRef(name_as_spoken: str, city: str | None = None, match: str = "new", confidence: Literal["high","low"] = "high")`;
  `PieceResult(intent: Literal["order_changes","bill_order","mark_shipped","record_payment","unclear"],
  customer: CustomerRef | None, changes: list[Change] = [], amount: PositiveInt | None = None, uncertain: list[str] = [])`.

- [ ] **Step 1: Write failing tests:** `test_parses_mixed_changes` (a dict with one of each op parses to the right
  classes); `test_negative_quantity_rejected` (`sizes={"M": -2}` raises `ValidationError`);
  `test_unknown_op_rejected`; `test_payment_set_field` (`SetField(op="set_field", field="payment", value="credit")`);
  `test_piece_result_json_schema_exists` (`PieceResult.model_json_schema()["title"] == "PieceResult"`, used in S3).
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement** the models exactly as in Interfaces.
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat: change-list models for AI output`.

### Task 5: Order engine (apply changes, rules, GST, totals, missing fields)

**Files:**
- Create: `app/domain/order.py`, `app/domain/rules.py`, `tests/domain/test_order_engine.py`

**Interfaces:**
- Consumes: `Catalog`, `Item` (Task 3); `Change` models (Task 4).
- Produces:
  - `OrderLine` (dataclass: `item_code: str, sizes: dict[str, int], quantity: int, rate_paise: int,
    flags: list[str], source_piece_id: int | None = None`)
  - `Order` (dataclass: `id: int | None, customer_name: str, city: str | None, state: Literal["open","billed","shipped","cancelled"],
    transport: str | None, payment: Literal["cash","upi","credit"] | None, lines: list[OrderLine]`)
  - `DiffEntry` (dataclass: `kind: Literal["added","changed","removed","set"], item_code: str | None, field: str | None,
    before: str | None, after: str | None`)
  - `ApplyResult` (dataclass: `order: Order, diff: list[DiffEntry], problems: list[str]`)
  - `apply_changes(order: Order, changes: list[Change], catalog: Catalog) -> ApplyResult` (pure; never mutates input)
  - `rules.line_flags(line: OrderLine, item: Item) -> list[str]`; flags: `below_min`, `sizes_missing`, `rate_off_list`
  - `Totals` (dataclass: `subtotal_paise: int, gst_paise: int, total_paise: int, line_totals: dict[str, int]`)
  - `compute_totals(order: Order, catalog: Catalog) -> Totals`
  - `missing_fields(order: Order) -> list[str]` from `["customer", "lines", "transport", "payment"]` in that order
  - `normalise_payment(value: str) -> Literal["cash","upi","credit"] | None` (accepts "credit", "kadan", "udhaar",
    "cash", "UPI", "gpay")

Behaviour the tests pin:
- `add_line` for an item already in the order **merges** sizes (adds per size) and quantity; else appends.
- Quantity = sum of sizes when sizes given, else `quantity_total`.
- Rate = `rate_spoken * 100` if given, else the list rate.
- Unknown item (`item_code` not in catalogue and `match(name_as_spoken)` is None) → problem
  `"Unknown item: <name_as_spoken>"`, nothing added.
- `change_line` replaces given fields; a size set to 0 is removed; item not in order → problem
  `"Not in order: <code>"`.
- `remove_line` removes; missing → problem.
- `set_field payment` uses `normalise_payment`; unrecognised → problem `"Unclear payment: <value>"`.
- Flags recomputed for every line after changes.

- [ ] **Step 1: Write failing tests** (use `Catalog.load("data/items.json")`):
  - `test_new_order_from_piece1`: empty order + add PRP qty 24 + add CRT S6 M6 L6 → 2 lines; diff has 2 `added`;
    `compute_totals` → subtotal ₹2,982.00 (`298200`), gst `14910`, total `313110`.
  - `test_piece2_merges_and_changes`: then add KPS S10 M10 L10 + change CRT to S12 M12 L12 → 3 lines (CRT still one
    line, quantity 36); totals subtotal `793200`, gst `39660`, total `832860`.
  - `test_same_item_added_twice_merges` (Review Focus 1).
  - `test_unknown_item_reported_not_added` (Review Focus 2).
  - `test_size_zero_removes_size`.
  - `test_below_min_flag`: CRT S4 → `below_min`; PRP quantity 20 → `below_min`; KPS quantity_total 30 without sizes →
    `sizes_missing`.
  - `test_rate_off_list_flag`: PRP rate_spoken 58 → `rate_off_list`; rate_spoken 70 → no flag.
  - `test_gst_18_percent_above_2500`: a line at rate ₹3,000 × 1 → gst `54000`.
  - `test_missing_fields`: new order with lines only → `["transport", "payment"]`; after set transport KPN and payment
    credit → `[]`.
  - `test_apply_is_pure`: input order unchanged after `apply_changes`.
- [ ] **Step 2: Run** `python -m pytest -q tests/domain/test_order_engine.py` → FAIL.
- [ ] **Step 3: Implement** `rules.py` then `order.py`. GST per line: `round_half_up(line_total * pct / 100)` using
  integer arithmetic (`(line_total * pct + 50) // 100`).
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat: order engine with merge, minimums, rate flags and GST in paise`.

### Task 6: Store and piece service (the piece state machine)

**Files:**
- Create: `app/store/__init__.py`, `app/store/db.py`, `app/flow/__init__.py`, `app/flow/readback.py`,
  `app/flow/pieces.py`, `tests/flow/__init__.py`, `tests/flow/test_pieces.py`

**Interfaces:**
- Consumes: `Order`, `apply_changes`, `compute_totals`, `missing_fields` (Task 5); `PieceResult` (Task 4); `Catalog`.
- Produces:
  - `Store(db_path: str)`: creates tables `customers, orders, order_lines, voice_pieces, order_events, traces` (RFC §5;
    no invoices/khata yet) on init, creating parent folders; methods `open_orders() -> list[Order]`,
    `get_order(order_id: int) -> Order | None`, `save_order(order: Order) -> int`, `add_piece(transcript: str,
    source: Literal["live","sample"], audio_path: str | None) -> int`, `get_piece(piece_id: int) -> dict`,
    `update_piece(piece_id: int, **fields) -> None`, `add_event(order_id: int, piece_id: int, change_json: str) -> None`,
    `count_pieces(source: str) -> int`, `reset() -> None` (deletes all rows; used by sample reset)
  - `readback.build_readback(order: Order, diff: list[DiffEntry], totals: Totals, missing: list[str], catalog: Catalog) -> str`
    (English for now; Tamil in S4). Example for sample piece 1:
    `"Kerala Fancy, Palakkad. Added: Print palazzo 24 at ₹68. Added: Crop top S 6, M 6, L 6 at ₹75. Order total ₹3,131.10 with GST. Still needed: transport, payment. Say sari to confirm."`
  - `Proposal` (dataclass: `piece_id: int, order_id: int | None, is_new_order: bool, order: Order, diff: list[DiffEntry],
    totals: Totals, missing: list[str], problems: list[str], readback: str, ask_customer: bool`)
  - `PieceService(store: Store, catalog: Catalog)` with `propose(transcript: str, result: PieceResult,
    source: str, audio_path: str | None = None) -> Proposal`, `confirm(piece_id: int) -> Order`,
    `discard(piece_id: int) -> None`; raises `PieceStateError` when confirm/discard is called on a piece not in
    `read_back`.
  - Target routing `resolve_target(ref: CustomerRef, open_orders: list[Order]) -> Order | None`: if `ref.match` is the id
    of an open order → it; else an open order whose normalised customer name equals the normalised `name_as_spoken`
    → it; else `None` (new order). `ref.confidence == "low"` → `ask_customer=True` and nothing proposed for apply.

- [ ] **Step 1: Write failing tests:**
  - `test_three_pieces_build_one_order`: propose+confirm the 3 sample results (built inline from the Task 7 fixture
    values) → `open_orders()` has exactly 1 order for "Kerala Fancy" with 3 lines, transport "KPN", payment "credit",
    totals total `832860`.
  - `test_nothing_applied_before_confirm`: propose piece 1 → `open_orders() == []`.
  - `test_confirm_twice_raises` and `test_confirm_discarded_raises` (Review Focus 3).
  - `test_billed_customer_starts_new_order` (Review Focus 4): save an order for "Kerala Fancy" with `state="billed"`,
    propose a piece for "Kerala Fancy" → `is_new_order is True`.
  - `test_low_confidence_asks_customer`.
  - `test_lines_record_source_piece`: after the 3 pieces, CRT line's `source_piece_id` is piece 2's id (last change),
    PRP's is piece 1's.
  - `test_readback_piece1_text`: equals the example string above.
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement.** Proposal state stored on the piece row (`state='read_back'`, `ai_result_json`,
  `proposal_json` = the resulting order snapshot). `confirm` writes the snapshot via `save_order`, sets
  `source_piece_id` on added/changed lines, adds an `order_events` row, sets the piece `state='applied'`.
- [ ] **Step 4: Run** → PASS.
- [ ] **Step 5: Commit** `feat: piece state machine with routing, read-back and confirm`.

### Task 7: Sample conversation and API

**Files:**
- Create: `app/sample/__init__.py`, `app/sample/conversation.json`, `app/api.py`, `tests/test_sample_api.py`
- Modify: `app/main.py` (include the API router; build `Store` and `PieceService` in `create_app`)

**Interfaces:**
- Consumes: `PieceService`, `Store` (Task 6); `PieceResult` (Task 4).
- Produces HTTP API:
  - `POST /api/sample/reset` → `{"ok": true}` (clears store)
  - `POST /api/sample/next` → `{"label": "Sample: saved AI results", "index": 1-3, "total": 3, "transcript": str,
    "proposal": <Proposal as JSON with money as paise plus formatted strings>}`; after piece 3 → HTTP 409
    `{"detail": "Sample finished"}`
  - `POST /api/pieces/{piece_id}/confirm` → order JSON; 409 on `PieceStateError`
  - `POST /api/pieces/{piece_id}/discard` → `{"ok": true}`; 409 on `PieceStateError`
  - `GET /api/orders` → list of `{id, customer_name, city, state, line_count, total_paise, total}`
  - `GET /api/orders/{id}` → order with lines (name, sizes, quantity, rate, line total, flags) and totals; 404 if none

`conversation.json` holds 3 pieces, each `{"transcript": ..., "ai_result": <PieceResult JSON>}`:
1. `"கேரளா ஃபேன்சி, பாலக்காடு. Print palazzo ரெண்டு dozen. Crop top S M L ஒவ்வொன்னும் six."` → customer
   Kerala Fancy / Palakkad / match "new"; add PRP quantity_total 24; add CRT sizes S6 M6 L6.
2. `"Kerala Fancy-க்கு kids palazzo set S M L ஒவ்வொன்னும் பத்து add பண்ணுங்க. Crop top twelve ஆக்குங்க."` →
   match "existing"; add KPS S10 M10 L10; change CRT sizes S12 M12 L12.
3. `"Kerala Fancy, KPN transport, credit."` → match "existing"; set transport KPN; set payment credit.

- [ ] **Step 1: Write failing tests:** `test_sample_full_run` (reset → next/confirm ×3 → `GET /api/orders` has one
  order, total_paise `832860`); `test_sample_label_present`; `test_sample_finished_409`;
  `test_confirm_twice_409`; `test_get_missing_order_404`.
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement** the router; `next` uses `store.count_pieces("sample")` to pick the index.
- [ ] **Step 4: Run** the whole suite `python -m pytest -q` → PASS.
- [ ] **Step 5: Commit** `feat: sample conversation API runs the real engine without keys`.

### Task 8: UI for the sample flow

**Files:**
- Modify: `app/static/index.html`, `app/static/app.js`, `app/static/styles.css`
- Test: `tests/test_app_starts.py` (add `test_static_assets_served`)

**Interfaces:**
- Consumes: the Task 7 HTTP API.

Screen (mobile-first, WhatsApp-like green header):
- Banner (Task 1). Disabled mic button with "key not set".
- `Try the sample conversation` → calls reset, then shows a **Next piece** button.
- Each piece: a chat bubble with the transcript and the grey label `Sample: saved AI results`; a proposal card with the
  order's lines (item name, sizes, quantity, rate, line total), **added lines green, changed lines amber**, flags as
  small badges, problems in red, totals (subtotal, GST, total), "Still needed: …", the read-back text, and two big
  buttons **Sari ✔** (confirm) and **Vendaam ✖** (discard).
- An **Orders** panel listing open orders (customer, city, lines, total), refreshed after each confirm.

- [ ] **Step 1: Write failing test** `test_static_assets_served`: `/static/app.js` and `/static/styles.css` return 200.
- [ ] **Step 2: Run** → FAIL only if assets are missing (they exist from Task 1, so this passes; keep it as a guard).
- [ ] **Step 3: Implement** the screen in plain JS (`fetch`, no framework).
- [ ] **Step 4: Verify in a browser** (Playwright MCP): start uvicorn; open `/`; banner visible; run the sample 3 times
  with Sari ✔; the Orders panel shows one order "Kerala Fancy" total `₹8,328.60`; take a screenshot to
  `docs/round2/screens/s1-sample.png`.
- [ ] **Step 5: Commit and push** `feat: sample conversation screen`; check CI green (`gh run list --limit 1`).

---

## Self-review notes

- Spec coverage for S0/S1: R4 (Tasks 3, 5), R7 (Task 6), R8 (Tasks 5, 6), R11 data link `source_piece_id` (Task 6),
  R12 (Tasks 1, 7, 8), R13 (Task 2), compliance gate CI (Task 2). R1-R3, R5 (live), R6, R9, R10, R14 belong to later
  slices.
- Arithmetic checked: piece 1 = 24 × ₹68 + 18 × ₹75 = ₹2,982.00 + GST ₹149.10 = **₹3,131.10**; after piece 2 =
  ₹1,632 + 36 × ₹75 + 30 × ₹120 = ₹7,932.00 + GST ₹396.60 = **₹8,328.60**.
- README with Mermaid diagrams (owner's request, 27 Nov): Task 2 writes it; Task 8 updates it with the screenshot.
