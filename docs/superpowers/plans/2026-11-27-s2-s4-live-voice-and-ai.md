# S2-S6: Voice Agent, Bill, Khata and Ask Implementation Plan (revised 27 Nov evening)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** the owner talks to Order Kural in Tamil, Hindi, Malayalam or Kannada, or uploads a buyer's voice note, or
types. A bounded voice agent then:
- builds the customer's order from pieces;
- reads it back in the owner's language;
- saves only after "sari";
- turns "bill it" into a numbered bill, a packing list and a khata debit;
- records payments;
- answers three spoken questions about the shop.

Every step is grounded in code, timed, costed and measured.

**Architecture:**
- **Pure domain code** in `app/domain/` covers order, bill and khata.
- **Shop services** in `app/flow/` handle staging and confirm, bill, payment, ship and ask.
- **`AgentSession`** in `app/agent/` exposes these as about 10 tools. Each tool returns `facts` and a code-built `say`
  sentence.
- **Two brains drive the same `AgentSession`:**
  - a **text loop**, calling Sarvam chat with tools, for typed input, uploaded notes and the eval;
  - a **Pipecat live voice pipeline** (Sarvam realtime STT → sarvam-105b with tools → Bulbul TTS), mounted on a
    FastAPI WebSocket.
- **After a write tool, the code's `say` is spoken directly** (`run_llm=False` plus `TTSSpeakFrame`), so the agent
  can't describe changes that didn't happen.

**Tech Stack:** as S0-S1, plus:
- `httpx==0.28.1` (runtime);
- `python-multipart==0.0.20`;
- `pipecat-ai[websocket,sarvam]==1.17.0`;
- ffmpeg (Docker image; `imageio-ffmpeg==0.6.0` in requirements-dev).

**Spec:** `docs/superpowers/specs/2026-11-27-order-book-that-listens-design.md`, the binding authority, especially
§2, §5, §5b and §7. Background: `docs/round2/04-rfc.md`, `docs/round2/03-prd.md`, `docs/round2/01-discovery.md`
§6c-6e. Spike code (throwaway, git-ignored, read-only reference): `spikes/pipecat/bot.py`, `index.html` and
`talk_test.py`.

## Findings this plan must answer

**Probe (27 Nov), sarvam-105b on the real Hindi note:**
1. It invented the customer "Sir".
2. It mapped "women's pant" to GPT.
3. It put age bands in the name.
4. It left transport and payment in `uncertain`.

Findings 1 and 2 are fixed in Tasks 1-2. Findings 3 and 4 go into the agent prompt examples and the eval.

**Spike (27 Nov):**
- **Worked:**
  - first reply 0.35-0.9 s after the end of speech;
  - Pipecat ran inside FastAPI;
  - a correct `add_to_order` from Tamil;
  - `confirm_order` on "சரி".
- **Failed:**
  - it once *said* "added, credit, ₹1,560" without calling any tool;
  - STT garbled "crop top M pathu" into "Groptop May 10";
  - customer names absorbed numbers ("Kerala Fancyku Irupati Nalu") until the prompt forbade it.

## Global Constraints

- Everything from S0-S1 still holds:
  - no-key start and banner text;
  - money in paise;
  - "nothing changes without confirm";
  - port 8000;
  - `ORDER_KURAL_DB`.
- **No tax maths anywhere the user sees.**
  - The bill and slip show quantity × rate = amount, the total and HSN codes.
  - The bill title is `Order bill (estimate)` with the footer `Tax as per final invoice`.
  - `compute_totals` GST fields stay in code and tests but are never rendered.
- **Keys and no-key behaviour:**
  - Keys are read at call time from `SARVAM_API_KEY`.
  - With no key:
    - HTTP endpoints that need Sarvam return 503 `{"detail": "Sarvam API key not set"}`;
    - `/api/voice` accepts the socket and then closes it with code 4003, reason `Sarvam API key not set`;
    - the sample still works.
- **Sarvam endpoints and settings:**
  - **Batch STT:** `POST https://api.sarvam.ai/speech-to-text` (multipart `file`, `model=saaras:v4`, `mode=codemix`,
    `language_code=unknown`).
  - **Chat:** `POST https://api.sarvam.ai/v1/chat/completions` (`model=sarvam-105b`, `temperature=0.2`, `tools`,
    `tool_choice="auto"`).
  - **TTS:** `POST https://api.sarvam.ai/text-to-speech` (`model=bulbul:v3`, `speaker=priya`,
    `speech_sample_rate=16000`).
  - **Live:** `SarvamRealtimeSTTService(endpointing="vad", model saaras:v4, mode codemix)`;
    `SarvamLLMService(model="sarvam-105b", reasoning_effort="none", temperature=0.2)`;
    `SarvamTTSService(model="bulbul:v3", voice="priya", sample_rate=16000)`.
  - The header is always `api-subscription-key`.
  - Timeouts: STT 60 s, chat 45 s, TTS 30 s.
- Batch STT takes at most 30 s per request, so split into chunks of at most 28 s, cutting at silences (ADR-004).
- **Cost estimates** (label them "estimated"; store paise, rounded up):
  - STT ₹0.49 per minute;
  - chat ₹10 per 1M input tokens and ₹25 per 1M output tokens;
  - TTS ₹2.5 per 1,000 characters.
- **Languages:**
  - Spoken and read-back languages are `ta-IN`, `hi-IN`, `ml-IN`, `kn-IN` and `en-IN`.
  - Read-back sentences are code templates, never AI-written.
  - Malayalam and Kannada templates are marked "check with a native speaker" in `app/agent/say.py`.
- **Confirm words** (`classify`): `confirm_pending` only acts when the user's last utterance classifies as `yes`.
  - **yes:** sari, seri, saari, aamaa, aama, haan, ha, theek hai, ok, okay, confirm, correct, howdu, houdu, sheri, athe,
    சரி, ஆமா, हाँ, हां, ठीक है, ശരി, ಹೌದು, ಸರಿ.
  - **no:** vendaam, vendam, venda, cancel, nahi, nahin, no, beda, venda, വേണ്ട, ಬೇಡ, வேண்டாம், नहीं.
- **Live-link cost guard:**
  - at most 30 text or upload turns per IP per hour, and 300 per day overall;
  - at most 6 voice sessions per IP per hour;
  - each voice session ends after 10 minutes;
  - beyond these, HTTP 429 or a WebSocket close with code 4029.
- Audio is saved to `data/runtime/audio/` and never committed. Sample audio lives in `app/sample/audio/`
  (synthetic, labelled) and is committed.

## Review Focus

1. **The agent claims a change that no tool made.** After any write tool, the spoken text equals the tool's `say`
   (test in Task 9 and the voice adapter in Task 11). The eval counts free-text claims (Task 15).
2. **"Sari" said with nothing pending, or the LLM calling `confirm_pending` after "also add 10 shorts".** Nothing is
   saved, and the say is "Nothing is waiting for sari" or "Say sari to save" (Task 9).
3. **A second customer's order starts while the first is still waiting for sari.** The first stays pending; the agent
   says "First say sari or cancel for Kerala Fancy" (Task 9).
4. **Billing an order with zero lines, billing twice, or a payment larger than the balance.**
   - Zero lines: "Nothing to bill for X".
   - Billing twice: the second "bill it" bills the new open order or says "No open order".
   - Overpayment: allowed, and the balance shows as an advance (negative) (Tasks 5-6).
5. **The voice socket dropping mid-pending** (closed tab, network). The staged piece stays `read_back` in the DB, is
   not applied, and shows as "waiting" in the UI on the next visit (Task 11).

---

### Tasks 1-3: done (see the ledger)

1. Honesty fixes and the `CustomerRef` contract.
2. Guardrails: near-miss customers, contradicting item codes, closest-item hints.
3. Isolated per-tab sample sessions (`X-Sample-Session`).

### Task 4: Provider protocols, tracing and cost

**Files:**
- Create: `app/providers/__init__.py`, `app/providers/base.py`, `app/providers/costs.py`, `app/obs/__init__.py`,
  `app/obs/trace.py`
- Modify: `app/store/db.py` (traces columns: `piece_id, span, provider, ms, cost_paise, ok, error, meta_json`)
- Test: `tests/test_trace.py`

**Interfaces:**
- Produces:
  - `Transcript(text: str, language: str, seconds_audio: float)`;
  - `class SpeechToText(Protocol): def transcribe(self, wav_path: Path) -> Transcript`;
  - `class TextToSpeech(Protocol): def speak(self, text: str, language: str) -> bytes` (WAV);
  - `ProviderError(Exception)`, whose message is safe to show;
  - `costs.stt_paise(seconds: float) -> int`, `costs.chat_paise(inp: int, out: int) -> int`,
    `costs.tts_paise(chars: int) -> int`, all rounding up;
  - `trace.span(store, piece_id: int | None, name: str, provider: str)`, a context manager:
    - it yields a dict where the caller may set `cost_paise` and `meta`;
    - it records ms, ok and the error text on exception, then re-raises;
  - `Store.traces_for(piece_id: int) -> list[dict]` and `Store.recent_traces(limit: int = 50) -> list[dict]`.

- [ ] **Step 1: Failing tests:**
  - `test_span_records_time_and_cost`;
  - `test_span_records_error_and_reraises`;
  - `test_costs_round_up`: `stt_paise(60) == 49`, `chat_paise(429, 531) == 2`, `tts_paise(1000) == 250`.
- [ ] **Steps 2-4:** FAIL → implement → PASS.
- [ ] **Step 5: Commit** `feat: provider protocols, traces and cost estimates`.

### Task 5: Bill and packing list (no tax maths)

**Files:**
- Create: `app/domain/bill.py`, `app/flow/shop.py`, `tests/domain/test_bill.py`, `tests/flow/test_shop.py`
- Modify: `app/store/db.py`, which gains:
  - table `bills(id, number UNIQUE, order_id, customer_id, total_paise, lines_json, created_at, voided INTEGER DEFAULT 0)`;
  - `Store.next_bill_number() -> int`, `Store.save_bill(...) -> int`, `Store.get_bill(number) -> dict | None`;
  - `Store.set_order_state(order_id, state)`;
  - `Store.orders_in_states(states: list[str]) -> list[Order]`.

**Interfaces:**
- Produces:
  - `BillLine(item_code, name, hsn, qty_text, quantity, rate_paise, amount_paise)`;
  - `Bill(number: int, order_id: int, customer_name: str, city, transport, payment, lines: list[BillLine],
    total_paise: int, created_at: str)`;
  - `bill.make_bill(order: Order, catalog: Catalog, number: int, created_at: str) -> Bill`, where amount = quantity ×
    rate;
  - `bill.packing_list(order: Order, catalog: Catalog) -> list[tuple[str, str, int]]`, giving (item name, size or "-",
    qty) with one row per size;
  - `bill.share_text(bill: Bill) -> str`: plain text with the title `Order bill (estimate) No. {n}`, one line per item,
    `Total ₹…` and `Tax as per final invoice`;
  - `ShopService(store, catalog)` with `issue_bill(order_id: int) -> Bill`. In one `store.tx()`, it:
    - checks there is at least one line (else `ShopError("Nothing to bill for {customer}")`);
    - takes the next number;
    - saves the bill;
    - sets the order state to `billed`;
    - adds the khata debit, but only once Task 6 exists. Until then this is a seam:
      `self._on_billed(bill)`, a no-op.

- [ ] **Step 1: Failing tests:**
  - `test_bill_amounts_no_gst`: a sample order gives a total of 24×6500 + 20×7500 paise, and there are no `gst`
    fields on `Bill`;
  - `test_packing_list_one_row_per_size`;
  - `test_share_text_has_estimate_title_and_footer`;
  - `test_issue_bill_numbers_increase_and_lock_order`: the order state becomes `billed` and is no longer in
    `open_orders()`;
  - `test_issue_bill_empty_order_raises`.
- [ ] **Steps 2-4:** FAIL → implement → PASS (full suite).
- [ ] **Step 5: Commit** `feat: numbered order bill and packing list (no tax maths)`.

### Task 6: Khata ledger, payments, shipping and undo

**Files:**
- Create: `app/domain/khata.py`, `tests/domain/test_khata.py`
- Modify:
  - `app/store/db.py`: table
    `ledger_entries(id, customer_id, kind TEXT CHECK(kind IN ('bill','payment','reversal')), amount_paise INTEGER, ref_bill INTEGER, mode TEXT, reverses INTEGER, created_at)`;
    plus `add_ledger(...) -> int`, `ledger_for(customer_id) -> list[dict]` and `last_ledger(customer_id) -> dict | None`;
  - `app/flow/shop.py`;
  - `tests/flow/test_shop.py`.

**Interfaces:**
- Produces:
  - `khata.balance(entries: list[dict]) -> int`: positive means the buyer owes;
    - a bill adds its amount;
    - a payment subtracts its amount;
    - a reversal negates the entry it reverses.
  - `ShopService.record_payment(customer_id: int, amount_paise: int, mode: Payment) -> int` (new balance);
  - `ShopService.mark_shipped(order_id: int, transport: str | None) -> None`: the state becomes `shipped`, and
    transport is set if given;
  - `ShopService.undo_last(customer_id: int) -> str`, which reverses the latest bill or payment that isn't already
    reversed:
    - for a bill, it also sets the bill to `voided=1` and the order back to `open`;
    - it returns a description such as "Bill 3 undone";
    - this is tap-only, with no voice tool.
  - `ShopService.balance(customer_id) -> int`.
  - `issue_bill` now adds the `bill` entry.

- [ ] **Step 1: Failing tests:**
  - `test_balance_bill_minus_payment`;
  - `test_overpayment_gives_negative_balance`;
  - `test_undo_payment_restores_balance`;
  - `test_undo_bill_voids_and_reopens_order`;
  - `test_undo_twice_reverses_previous_entry_not_the_reversal`;
  - `test_mark_shipped_sets_state_and_transport`.
- [ ] **Steps 2-4:** FAIL → implement → PASS.
- [ ] **Step 5: Commit** `feat: in-app khata with payments, undo by reversal, and shipping`.

### Task 7: Ask the shop (three questions, answered by code)

**Files:**
- Create: `app/flow/ask.py`, `tests/flow/test_ask.py`

**Interfaces:**
- Produces:
  - `Answer(kind: str, facts: dict)`;
  - `ask.to_ship(store, catalog) -> Answer`: orders in state `open` or `billed`; facts `{"orders":
    [{"customer", "bill_number" | None, "lines": n, "total_paise"}]}`;
  - `ask.customer_summary(store, catalog, order: Order | None, customer_id: int) -> Answer`: facts are the open order
    lines and the khata balance;
  - `ask.item_count(store, catalog, item_code: str, now: datetime, days: int = 7) -> Answer`: the sum of quantities in
    lines of orders created in the last `days`, in any state except `cancelled`.

- [ ] **Step 1: Failing tests:**
  - `test_to_ship_lists_open_and_billed_not_shipped`;
  - `test_customer_summary_has_balance`;
  - `test_item_count_last_7_days_only`.
- [ ] **Steps 2-4:** FAIL → implement → PASS.
- [ ] **Step 5: Commit** `feat: ask the shop: to ship, customer summary, item counts`.

### Task 8: Spoken sentences in five languages, and yes/no words

**Files:**
- Create: `app/agent/__init__.py`, `app/agent/say.py`, `app/agent/words.py`, `tests/agent/__init__.py`,
  `tests/agent/test_say.py`, `tests/agent/test_words.py`

**Interfaces:**
- Produces:
  - `words.classify(text: str) -> Literal["yes", "no", "other"]`:
    - it uses the Global Constraints lists on casefolded text with punctuation removed;
    - it matches whole words or phrases ("ok" in "book" is not yes);
    - when yes and no words both appear, the answer is `other`;
    - when a yes word sits alongside order words, it's still `yes` only if the text has at most 3 words.
  - `say.lang(code: str | None) -> str`: maps any STT code to one of `ta-IN`, `hi-IN`, `ml-IN`, `kn-IN` or `en-IN`
    (default `ta-IN`).
  - `say.render(kind: str, facts: dict, language: str) -> str` for these kinds:
    - `staged` (customer, changes, order total, problems, "say sari to save");
    - `saved`;
    - `discarded`;
    - `nothing_pending`;
    - `need_yes`;
    - `other_pending` (customer);
    - `ask_customer` (question);
    - `bill_staged` (number preview, total);
    - `bill_saved`;
    - `payment_staged`;
    - `payment_saved` (balance);
    - `shipped_staged`;
    - `to_ship`;
    - `customer_summary`;
    - `item_count`;
    - `cannot_answer`.

    Money is formatted as `₹26,552` (Indian grouping, no paise when they're zero). Numbers are digits in all
    languages.

- [ ] **Step 1: Failing tests:**
  - `test_classify_yes_tamil` ("சரி");
  - `test_classify_howdu_kannada`;
  - `test_classify_no_vendaam`;
  - `test_classify_book_is_not_ok`;
  - `test_classify_also_add_ten_shorts_is_other`;
  - `test_render_staged_tamil_has_total_and_sari`;
  - `test_render_every_kind_every_language_nonempty`, a parametrised loop over all kinds × 5 languages;
  - `test_money_format_indian_grouping` (`2655200` paise → `₹26,552`).
- [ ] **Steps 2-4:** FAIL → implement → PASS.
- [ ] **Step 5: Commit** `feat: code-built spoken sentences in five languages and yes/no words`.

### Task 9: AgentSession: the tools, staging and the confirm guard

**Files:**
- Create: `app/agent/session.py`, `app/agent/tools.py`, `tests/agent/test_session.py`

**Interfaces:**
- Consumes:
  - `PieceService.propose/confirm/discard`;
  - `ShopService` (Tasks 5-6);
  - `ask` (Task 7);
  - `say`, `words` (Task 8);
  - `resolve_target`, `near_matches`.
- Produces:
  - `ToolResult(facts: dict, say: str, ui: dict, wrote: bool)`, where `ui` is the slip state for the page.
  - `AgentSession(pieces: PieceService, shop: ShopService, source: str = "live")`, holding:
    - `pending: Pending | None`, where `Pending(kind: "order" | "bill" | "payment" | "ship", piece_id | None,
      customer: str, args: dict)`;
    - `language: str`;
    - `last_user_text: str`.
  - Tool methods, all returning `ToolResult`:
    - `find_customer(name, city=None)`;
    - `get_open_order(customer)`;
    - `add_to_order(customer, items, city=None)`;
    - `change_line(customer, item_code, sizes=None, quantity_total=None)`;
    - `remove_line(customer, item_code)`;
    - `set_detail(customer, field, value)`;
    - `bill_order(customer)`;
    - `record_payment(customer, amount_rupees, mode)`;
    - `mark_shipped(customer, transport=None)`;
    - `ask_shop(question: "to_ship" | "customer" | "item_count", customer=None, item=None)`;
    - `confirm_pending()`;
    - `discard_pending()`.
  - `AgentSession.heard(text: str, language: str | None)`, called by both brains before each LLM turn.
  - `tools.TOOL_SPECS: list[dict]`, OpenAI-style function JSON for all 12 tools, with descriptions saying when to use
    each.
- **Staging rules:**
  - **Order changes:**
    - The order-change tools build a `PieceResult(intent="order_changes", customer=CustomerRef(...), changes=[...])`.
    - If `pending` is an order for the **same** customer, the new piece contains the old changes plus the new ones:
      the old piece is discarded and the combined one proposed, so there is one pending piece per "sari".
    - If `pending` belongs to a **different** customer or kind, nothing is staged and the say is `other_pending`.
    - If `ask_customer` is true, nothing is pending and the say is `ask_customer` with the readback question.
  - **Bill, payment and ship** stage a `Pending` without touching the DB until confirmed. Payment and ship resolve the
    customer through `customers` by normalised name. If the customer is unknown, the say is `ask_customer`.
  - **`confirm_pending`:**
    - with no pending, the say is `nothing_pending`;
    - if `words.classify(last_user_text) != "yes"`, the say is `need_yes` and nothing changes;
    - otherwise it runs `PieceService.confirm` or the `ShopService` call, clears `pending`, and the say is `saved`,
      `bill_saved` or `payment_saved` (with balance).
  - `wrote=True` only for tools that staged or saved.

- [ ] **Step 1: Failing tests** (real in-memory `Store`, real catalogue; no network):
  - `test_add_to_order_stages_and_says_total`;
  - `test_second_add_same_customer_merges_into_one_pending`;
  - `test_other_customer_while_pending_is_refused`;
  - `test_confirm_requires_yes_words` (`heard("also add ten shorts")` then `confirm_pending()` → `need_yes`; DB
    unchanged);
  - `test_confirm_with_sari_saves`;
  - `test_confirm_with_nothing_pending`;
  - `test_bill_then_sari_issues_bill_and_debit`;
  - `test_payment_then_sari_updates_balance`;
  - `test_customer_not_said_asks_not_pending`;
  - `test_say_matches_render_for_staged` (the `say` equals `say.render("staged", facts, lang)`);
  - `test_tool_specs_cover_all_methods`.
- [ ] **Steps 2-4:** FAIL → implement → PASS (full suite).
- [ ] **Step 5: Commit** `feat: agent session with grounded tools, staging and a yes-word confirm guard`.

### Task 10: The text brain (Sarvam chat with tools), typing, and the prompt

**Files:**
- Create: `app/agent/prompt.py`, `app/agent/text_loop.py`, `tests/agent/test_prompt.py`,
  `tests/agent/test_text_loop.py`, `tests/test_agent_api.py`
- Modify: `app/api.py` (`POST /api/agent/text`), `app/main.py` (one `AgentSession` per browser `X-Agent-Session`
  header, in an LRU of 200 that shares the live `Store`), `requirements.txt` (`httpx==0.28.1`)

**Interfaces:**
- Produces:
  - `prompt.system_prompt(catalog: Catalog, open_orders: list[Order]) -> str`, containing:
    - the role, "reply in the owner's language, one or two short sentences";
    - the spike rules (Tamil number words; sizes, never in the name; the customer is the shop name only; transport is
      a carrier; payment is cash/upi/credit/bank);
    - "never say you added, saved or billed anything: the tools speak for themselves";
    - "if unsure, ask one short question";
    - the item list;
    - open orders as `#id customer, city`;
    - four worked examples taken from the probe: age bands into sizes; Girnar Transport and bank payment; no shop name
      means ask; an unknown item keeps its name with no code.
  - `TextBrain(session: AgentSession, api_key: str, client: httpx.Client | None = None)` with
    `turn(user_text: str, language: str | None = None) -> TurnResult`, where
    `TurnResult(spoken: list[str], tool_calls: list[dict], ui: dict, timings_ms: dict, cost_paise: int,
    error: str | None)`. It loops for at most 4 tool rounds:
    - a write tool's `say` is appended to `spoken` and the loop ends, with no extra LLM text;
    - a read tool's facts go back to the LLM, and its next text is spoken;
    - on an HTTP or timeout error, `error = "Couldn't understand that. Please say it again, or type it."`
  - `POST /api/agent/text {"text"}` returns `TurnResult` JSON. It gives 503 without a key and 429 from the rate
    limiter (`app/ratelimit.py`: `RateLimiter(per_ip_hour=30, per_day=300)`).
  - `POST /api/agent/confirm` and `/api/agent/discard` handle the **tap** Sari and Cancel buttons. They set
    `last_user_text="sari"` (or "cancel") and call the tool, so the tap is the human approval.

- [ ] **Step 1: Failing tests** (httpx `MockTransport` scripted responses):
  - `test_prompt_has_rules_items_examples`;
  - `test_write_tool_say_is_spoken_and_llm_not_called_again`;
  - `test_read_tool_result_goes_back_to_llm`;
  - `test_four_round_cap`;
  - `test_http_error_gives_exact_message`;
  - `test_request_has_tools_and_model` (`model == "sarvam-105b"`, `tool_choice == "auto"`);
  - `test_text_endpoint_503_without_key`;
  - `test_tap_confirm_saves`;
  - `test_rate_limit_429`.
- [ ] **Steps 2-4:** FAIL → implement → PASS.
- [ ] **Step 5: Real check (not CI; key from `.env`, never printed):** run three typed turns through `TextBrain`:
  1. "Kerala Fancy-ku 24 plain palazzo S 6 M 6 L 6 XL 6";
  2. "sari";
  3. the Hindi discovery §6d transcript.

  Ledger the tool calls and spoken text, good or bad.
- [ ] **Step 6: Commit** `feat: text brain with Sarvam tool calling, typing and tap confirm`.

### Task 11: The live voice brain (Pipecat on /api/voice)

**Files:**
- Create: `app/voice/__init__.py`, `app/voice/wire.py` (`RawPCMSerializer`), `app/voice/bot.py`,
  `tests/voice/__init__.py`, `tests/voice/test_wire.py`, `tests/voice/test_bot_tools.py`
- Modify: `app/api.py` (`@router.websocket("/voice")`), `requirements.txt` (`pipecat-ai[websocket,sarvam]==1.17.0`),
  `Dockerfile` if needed

**Interfaces:**
- Consumes: `AgentSession`, `tools.TOOL_SPECS`, `prompt.system_prompt` and `say`.
- Produces:
  - `RawPCMSerializer`: binary is PCM16 mono 16 kHz in both directions; text messages are JSON. Outgoing events:
    - `{"type":"user","text","lang"}`;
    - `{"type":"bot","text"}`;
    - `{"type":"slip", ...ui}`;
    - `{"type":"latency","s"}`;
    - `{"type":"clear"}` on interruption.

    Incoming JSON `{"type":"note","text"}` (an uploaded note's transcript) is injected as a user turn, and
    `{"type":"tap","action":"confirm"|"discard"}` runs the tap path.
  - `bot.run(ws, session: AgentSession, api_key: str)`, which builds the pipeline from the spike:
    - transport → STT → Tap → user aggregator (External turn strategies, timeout 0.3) → LLM → TTS → output →
      assistant aggregator;
    - one Pipecat handler per tool, wrapping the `AgentSession` method;
    - **a write tool** pushes `TTSSpeakFrame(result.say)` and returns with
      `FunctionCallResultProperties(run_llm=False)`;
    - **a read tool** returns its facts with `run_llm=True`;
    - **`confirm_pending`** is registered with `cancel_on_interruption=False`;
    - each `TranscriptionFrame` calls `session.heard(text, language)`, and when the language changes it pushes
      `TTSUpdateSettingsFrame` with that language.
  - **WebSocket rules:**
    - With no key, accept and then close with code 4003.
    - The rate limit is 6 sessions per IP per hour (close 4029).
    - Sessions are cancelled after 600 s.
    - **Pipecat is imported inside the handler**, so app start and keyless tests never import it.
  - **Verify while implementing:** the exact 1.17 names (`FunctionCallResultProperties`, `TTSSpeakFrame`,
    `TTSUpdateSettingsFrame`, the `params.result_callback(result, properties=...)` signature) against the installed
    package or the Context Hub. Ledger any difference as a ruling.

- [ ] **Step 1: Failing tests (no network):**
  - `test_serializer_pcm_roundtrip`;
  - `test_serializer_note_message_becomes_user_text`;
  - `test_write_tool_handler_speaks_say_without_llm` (a fake `FunctionCallParams` records the pushed frames and the
    properties);
  - `test_voice_ws_closes_4003_without_key` (TestClient websocket).
- [ ] **Steps 2-4:** FAIL → implement → PASS (full suite, with no key and without Pipecat import errors).
- [ ] **Step 5: Real check (not CI):**
  - Run `spikes/pipecat/talk_test.py` pointed at `ws://127.0.0.1:8000/api/voice`. Expected:
    - the Tamil order is staged;
    - "சரி" saves;
    - the spoken text after the write tools equals the `say`.
  - Ledger the latency numbers.
- [ ] **Step 6: Commit** `feat: live voice agent on Pipecat with grounded tool speech`.

### Task 12: Uploaded voice notes (batch STT at pauses)

**Files:**
- Create: `app/audio.py`, `app/providers/sarvam_stt.py`, `tests/test_audio.py`, `tests/providers/__init__.py`,
  `tests/providers/test_sarvam_stt.py`
- Modify: `app/api.py` (`POST /api/agent/upload`, multipart `audio`), `requirements.txt`
  (`python-multipart==0.0.20`), `requirements-dev.txt` (`imageio-ffmpeg==0.6.0`), `Dockerfile` (`apt-get install -y
  ffmpeg`), `.github/workflows/ci.yml` (install ffmpeg)

**Interfaces:**
- Produces: the same audio interfaces as the old Task 5:
  - `ffmpeg_exe`;
  - `to_wav16k(src, dst) -> float`;
  - `silences(wav)`;
  - `choose_cuts(duration, silences, max_len=28.0) -> list[float]`;
  - `split`;
  - `AudioError`;
  - `SarvamSTT(api_key, client=None)` implementing `SpeechToText`.

  `POST /api/agent/upload`:
  - saves the audio;
  - transcribes it;
  - calls `TextBrain.turn("Forwarded voice note from a buyer: " + transcript, language)`;
  - returns `TurnResult` plus `transcript`.

  It gives 422 for `AudioError` (silent, under 0.5 s, over 5 minutes, or undecodable) and 503 without a key. (When a
  live socket is open, the page instead sends `{"type":"note"}` over the socket with the transcript returned by
  `POST /api/agent/transcribe`.)

- [ ] **Step 1: Failing tests:**
  - `test_choose_cuts_prefers_silence` (`choose_cuts(35.8, [(17.6, 18.2)]) == [17.9]`);
  - `test_choose_cuts_hard_cut_without_silence` (`== [28.0, 56.0]` for 60 s);
  - `test_choose_cuts_short_audio`;
  - `test_to_wav16k_rejects_garbage`;
  - `test_sarvam_stt_joins_chunks`;
  - `test_sarvam_stt_5xx_raises_provider_error`;
  - `test_upload_garbage_422`;
  - `test_upload_runs_text_brain` (fake STT and fake brain).
- [ ] **Steps 2-4:** FAIL → implement → PASS.
- [ ] **Step 5: Real check:** upload `data/private/recordings/2026-11-27-customer-order-1.ogg`. Expected:
  - the agent asks which customer, because the note names no shop;
  - "Girnar Transport" appears once;
  - no duplicated "50 piece".

  Ledger the result.
- [ ] **Step 6: Commit** `feat: forwarded voice notes go to the agent (split at pauses, Sarvam STT)`.

### Task 13: The screen: talk, slip, sari, bill, packing list, khata

**Files:**
- Modify: `app/static/index.html`, `app/static/app.js`, `app/static/styles.css`, `app/api.py`
- Create: `app/static/voice.js` (the mic worklet and PCM player from the spike, plus socket events),
  `tests/test_pages_api.py`

**Interfaces:**
- **HTTP:**
  - `GET /api/bills/{number}` returns bill JSON plus `share_text`;
  - `GET /bill/{number}` returns a printable HTML page;
  - `GET /api/customers` returns `[{"id","name","city","balance_paise","balance"}]`;
  - `GET /api/customers/{id}/khata` returns the entries and the balance;
  - `POST /api/customers/{id}/undo` returns `{"message"}`.
- **The page:**
  - a big **Talk** button (opens `/api/voice`; when the key is missing, it shows "Sarvam API key not set: try the
    sample");
  - **Upload a voice note**;
  - **Type** a box;
  - a live conversation strip;
  - the **order slip**, showing "Waiting for sari" with **Sari** and **Cancel** tap buttons;
  - **Bills**, each with a **Share** button (`navigator.share`, else copy the text) and **Print**;
  - a **Packing list**;
  - **Khata**, showing balances and **Undo last**;
  - the page sends `X-Sample-Session` **only** on sample calls (the Task 3 ruling).

- [ ] **Step 1: Failing tests:**
  - `test_bill_page_has_estimate_title_and_no_gst` (the HTML contains `Order bill (estimate)` and
    `Tax as per final invoice`, and no `GST`);
  - `test_customers_list_balances`;
  - `test_undo_endpoint`;
  - `test_live_orders_listed_without_sample_header`.
- [ ] **Steps 2-4:** FAIL → implement → PASS.
- [ ] **Step 5: Browser check** (Playwright, at 420 px wide): typed order → slip → Sari → "bill it" → Sari → bill
  page. Screenshots go in `docs/round2/screens/`.
- [ ] **Step 6: Commit** `feat: talk screen with slip, tap confirm, bill, packing list and khata`.

### Task 14: The keyless sample tells the whole story

**Files:**
- Modify: `app/sample/conversation.json`, `app/api.py` (`/api/sample/next`), `app/static/app.js`
- Create: `scripts/make_sample_audio.py`, `app/sample/audio/*.wav`, `tests/test_sample_story.py`

**Interfaces:**
- Each sample step is `{"user_text", "language", "user_audio", "tool_calls": [{"name", "args"}], "bot_audio"}`.
  `/api/sample/next`:
  - runs the saved tool calls on that tab's `AgentSession` (in-memory store);
  - calls `heard(user_text)` first;
  - returns `{"label": "Sample: saved AI results · synthetic voice", "index", "total", "user_text", "spoken": [say…],
    "slip", "user_audio_url", "bot_audio_url"}`.
- **Steps:**
  1. Tamil order piece;
  2. Tamil addition, transport and credit;
  3. "சரி";
  4. a Hindi forwarded note (customer asked, so the next step says "Kerala Fancy");
  5. "bill it";
  6. "சரி";
  7. "Kerala Fancy paid 5,000 by UPI";
  8. "சரி";
  9. "What's still to ship?"
- `make_sample_audio.py` (key needed; run once) synthesises `user_text` and the expected `say` texts with Bulbul and
  writes the WAVs plus a `say_texts.json`.

- [ ] **Step 1: Failing tests:**
  - `test_sample_runs_all_steps_without_key`;
  - `test_sample_ends_with_bill_and_balance`;
  - `test_sample_bot_audio_text_matches_say` (the `say_texts.json` entries equal the runtime `say`, so the audio
    can't drift from the code).
- [ ] **Steps 2-4:** FAIL → implement → PASS.
- [ ] **Step 5:** Generate the audio (key set) and commit the WAVs. Ask the owner to check the Tamil wording.
- [ ] **Step 6: Commit** `feat: keyless sample plays the full order-to-khata story with synthetic voice`.

### Task 15: Eval set v1, including claims versus tool calls

**Files:**
- Create: `eval/__init__.py`, `eval/cases/*.json` (12 cases), `eval/score.py`, `eval/run.py`, `eval/README.md`,
  `docs/round2/05-evalset.md`, `tests/test_eval_score.py`

**Interfaces:**
- **Case format:** `{"id", "source": "real"|"synthetic", "language", "turns": [{"user_text"}], "gold_final": {"orders":
  [{"customer", "lines": [{"item_code", "sizes", "quantity"}], "transport", "payment", "state"}], "balances":
  {"customer": paise}}}`.
- **Produces:**
  - `score.score_case(case, run: CaseRun) -> CaseScore`;
  - `score.summary(scores)` → `final_order_acc`, `line_acc`, `silent_errors`, `false_claims`, `asked_when_needed`,
    `p50_ms` and `cost_paise_total`.
  - A **silent error** is a final line that differs from gold and was not flagged by a problem or an ask.
  - A **false claim** is a turn where the LLM's free text (not a tool `say`) contains a claim word but no write tool ran
    that turn. The claim words are: added, saved, billed, set, sērthu, சேர்த்து, panniten, पंजीकृत, जोड़, ചേർത്ത,
    ಸೇರಿಸ.
  - `python -m eval.run --brain text --out eval/reports/` writes a report from the text brain, with `heard()` and
    `confirm` driven by "sari" turns.
- **Cases (12):**
  - 1 real: the Hindi note;
  - 11 synthetic, labelled:
    - Tamil multi-piece;
    - a change and a removal;
    - a near-miss customer;
    - no shop name;
    - an unknown item;
    - an off-list rate;
    - bill, then payment;
    - "sari" without pending;
    - "also add ten shorts" during pending;
    - Malayalam;
    - Kannada.

- [ ] **Step 1: Failing tests:**
  - `test_perfect_run_scores_100`;
  - `test_wrong_quantity_unflagged_is_silent_error`;
  - `test_flagged_is_not_silent`;
  - `test_claim_without_tool_is_false_claim`;
  - `test_tool_say_is_not_a_claim`.
- [ ] **Steps 2-4:** FAIL → implement → PASS.
- [ ] **Step 5:** Run with the key and commit the report whatever it shows. Put the numbers and one paragraph of
  failure analysis into `05-evalset.md` and the README.
- [ ] **Step 6: Commit** `feat: eval set v1 with false-claim and silent-error scoring`.

### Task 16: Docker, docs and the halfway gate

**Files:**
- Modify: `README.md` (status table, architecture section rewritten for the agent, eval table, screenshots),
  `docs/round2/04-rfc.md` (a pointer to the design doc and the actual dates), `docs/round2/project-status.html`

- [ ] **Step 1:** Run `docker compose build` then `docker compose up` with no `.env`.
  - **Expected:** the main screen loads; Talk shows "key not set"; the sample plays fully.
  - Record the image size in the ledger. If Docker Desktop isn't available locally, rely on CI's compose job and say
    so.
- [ ] **Step 2: Halfway gate (key set, by hand):**
  1. talk in Tamil;
  2. upload the Hindi note;
  3. say "சரி";
  4. "bill it", then "சரி";
  5. a payment;
  6. "what is to ship?".

  Screenshot it, and record pass or fail honestly.
- [ ] **Step 3:** Update the README status, architecture (with a mermaid diagram of the agent and tools) and eval
  numbers.
- [ ] **Step 4:** Run `python -m pytest -q` → PASS. Push the branch. CI green.
- [ ] **Step 5: Commit** `docs: voice agent status, eval results and halfway gate`.

---

## Cut order if late (from the design, §7)

1. The WhatsApp share button (keep copy-text).
2. Malayalam and Kannada templates (fall back to `en-IN`).
3. `ask_shop` `item_count`.
4. `mark_shipped`.

Bill, packing list, khata, the live voice brain and the keyless sample are never cut.

## Self-review notes

- **Spec coverage:**

  | Design section | Tasks |
  |---|---|
  | §2 goals 1-7 | T9-T13 |
  | Bill, no tax | T5 + T13 |
  | Khata and undo | T6 + T13 |
  | Ask | T7 + T9 |
  | 4 languages | T8 |
  | Grounded replies | T9-T11, T15 |
  | Keyless story | T14 |
  | Decisions 1-7 of §7 | T9 (one sari per piece, merge), T6 (reversal), T5 (estimate title), T7 (7 days), T14 (Tamil + Hindi demo) |

- **Superseded old tasks:**
  - the old Task 6 extractor and its JSON schema are replaced by tool calling (T9-T10);
  - the old Task 7 endpoints are replaced by T10-T13;
  - the old Task 9 read-back and voice confirm are replaced by T8, T9 and T11.
- **Interface consistency:**
  - `ToolResult.say` is spoken in T10 and T11 and checked in T14 and T15;
  - `AgentSession.heard` is called by T10, T11 and T14;
  - `Pending.kind` covers bill, payment and ship, from T5-T6.
- **Open dependency:** women's and teen rates from the owner. Until they arrive, the real case's gold expects "asked
  or unknown item" for those lines.
