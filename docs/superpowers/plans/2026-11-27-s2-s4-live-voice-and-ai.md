# S2-S4: Live Voice, AI Understanding, Eval and Spoken Read-back Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** One real voice note (uploaded or held-to-talk) becomes a correct, read-back, voice-confirmed change to the
right customer's order, with every AI step validated, timed, costed and measured on an eval set; and nothing the
README claims is untrue.

**Architecture:** Providers (Sarvam STT, Sarvam chat extractor, Sarvam TTS) sit behind small protocols in
`app/providers/`; a fixture extractor keeps the no-key sample working. A `LivePieceService` path runs
audio → transcript → validated change list → existing `PieceService.propose`, recording one trace span per step.
Guardrails added in code catch the AI failure modes found in the 27 Nov probe. The eval runner scores conversations
through the same path.

**Tech Stack:** as S0-S1, plus `httpx==0.28.1` as a runtime dependency (Sarvam calls), `python-multipart==0.0.20`
(FastAPI uploads), ffmpeg (Docker image; `imageio-ffmpeg==0.6.0` in requirements-dev for local runs).

**Spec:** `docs/round2/04-rfc.md` (§4.1-4.6, §6, §8, §9, §12 S2-S4), `docs/round2/03-prd.md` (R1-R3, R5-R7, R14,
guardrails §8, metrics §7). Evidence: `docs/round2/01-discovery.md` §6d and the probe findings below. Review that
drove the order of tasks: the project evaluation of 27 Nov (summarised in the "Probe and review findings" section).

## Probe and review findings this plan must answer (27 Nov)

Real `sarvam-105b` call on the real Hindi customer note (2.95 s, 960 tokens, schema followed):
1. Invented customer "Sir" from the greeting: the note never names the shop.
2. Mapped "women's pant" to `GPT` (Girls pant): a wrong item applied silently.
3. Put age bands ("1 से 10 साल") into `name_as_spoken` with `quantity_total`, instead of `sizes`.
4. Put "Girnar Transport" and the bank payment into `uncertain` instead of `set_field`.

Review: no voice in the running app; README and RFC over-claim; no eval; near-miss customer names start a silent new
order; no failure state; sample reset wipes shared data on a live link; no latency or cost numbers.

## Global Constraints

- Everything from the S0-S1 plan still holds (no-key start, banner text, paise, GST, "nothing changes without
  confirm", port 8000, `ORDER_KURAL_DB`).
- Keys are read at call time from env `SARVAM_API_KEY`; with no key, live endpoints return HTTP 503
  `{"detail": "Sarvam API key not set"}` and the sample still works.
- Sarvam endpoints (verified 27 Nov): STT `POST https://api.sarvam.ai/speech-to-text` (multipart `file`, `model=saaras:v4`,
  `mode=codemix`, `language_code=unknown`; response `transcript`, `language_code`); chat
  `POST https://api.sarvam.ai/v1/chat/completions` (`model=sarvam-105b`, `reasoning_effort=null`, `temperature=0.2`,
  `response_format={"type":"json_schema","json_schema":{"name":"PieceResult","schema":<PieceResult schema>,"strict":true}}`);
  TTS `POST https://api.sarvam.ai/text-to-speech` (`text`, `target_language_code`, `model=bulbul:v3`; response
  `audios[0]` base64 WAV). Header `api-subscription-key`. Timeouts: STT 60 s, chat 45 s, TTS 30 s.
- STT takes at most 30 s per request: split audio into chunks of at most 28 s, cutting at silences (ADR-004).
- Cost estimates (RFC §6 list prices; label them "estimated"): STT ₹0.49 per minute of audio; chat ₹10 per 1M
  input tokens and ₹25 per 1M output tokens; TTS ₹2.5 per 1,000 characters. Store in paise, rounded up.
- Audio saved to `data/runtime/audio/<piece_id>.<ext>`; never committed. Sample audio lives in `app/sample/audio/`
  and is committed (synthetic voice, labelled).
- Read-back languages: `ta-IN`, `hi-IN`, `en-IN`; templates are code, never AI-written.
- Confirm words (RFC §4.5): yes = sari, seri, saari, aamaa, aama, haan, ha, theek hai, ok, okay, confirm, சரி, ஆமா,
  हाँ, हां, ठीक है; no = vendaam, vendam, venda, cancel, nahi, nahin, no, வேண்டாம், नहीं.
- Live-link cost guard: at most 30 live pieces per client IP per hour and 300 per day overall; then HTTP 429.

## Review Focus

1. **A forwarded customer note that never names the shop** must leave the piece asking "Which customer is this for?",
   never inventing a customer (probe finding 1).
2. **An AI item code that contradicts the spoken name** ("women's pant" → GPT) must be reported as a problem and the
   line not added (probe finding 2).
3. **Audio that is silent, under 0.5 s, over 5 minutes, or not decodable** must return a clear HTTP 422 message, never
   a 500 or a stuck piece.
4. **A provider timeout, 5xx or invalid JSON twice** must end in the "Couldn't understand, please say it again" state
   with the piece in state `failed`, and the trace shows the error.
5. **A spoken reply that is neither yes nor no** ("also add ten shorts") must not confirm the pending piece; it is
   treated as a new piece.

---

### Task 1: Honesty fixes (README, RFC, contract)

**Files:**
- Modify: `README.md`, `docs/round2/04-rfc.md` (§4.8 wording), `app/domain/changes.py`, `app/flow/pieces.py`,
  `app/sample/conversation.json`, `tests/domain/test_changes.py`, `tests/flow/test_pieces.py`

**Interfaces:**
- Produces: `CustomerRef(name_as_spoken: str | None = None, city: str | None = None,
  match: Literal["new", "existing"] = "new", order_id: int | None = None, confidence: Literal["high","low"] = "high")`.
  `candidates()` uses `order_id` when given, else the name rules. A `CustomerRef` with no `name_as_spoken` and no
  `order_id` means "customer not said".

- [ ] **Step 1: Failing tests:** `test_customer_match_rejects_free_text` (`match="existing-ish"` raises);
  `test_order_id_routes_directly` (propose with `order_id` of an open order targets it even if the name differs);
  `test_customer_not_said_asks` (customer `{"match": "new"}` with no name → `ask_customer is True`, piece state `proposed`).
- [ ] **Step 2: Run** → FAIL.
- [ ] **Step 3: Implement** the contract change; update fixtures (`"match": "existing"`).
- [ ] **Step 4: README:** add a "What works today / Planned" table: built = no-key start, order engine, confirm,
  sample; planned (with slice) = live voice S2, AI S3, spoken read-back S4, bill and khata S5. Change the sequence
  diagram title to "How an order is built (target design; live voice in progress)". Remove "each line can be traced to
  the voice note it came from" until Task 6 stores audio. RFC §4.8: "three sample pieces with saved AI results; audio
  is synthetic (Task 9)".
- [ ] **Step 5: Run** `python -m pytest -q` → PASS. **Commit** `fix: honest README and explicit customer match contract`.

### Task 2: Guardrails for the probe failures (customer near-miss, item mismatch)

**Files:**
- Modify: `app/flow/pieces.py`, `app/domain/order.py`, `app/domain/catalog.py`
- Test: `tests/flow/test_pieces.py`, `tests/domain/test_order_engine.py`

**Interfaces:**
- Produces: `catalog.Catalog.closest(spoken: str, n: int = 3) -> list[Item]` (difflib, cutoff 0.5);
  `pieces.near_matches(ref: CustomerRef, open_orders: list[Order]) -> list[Order]` (difflib ratio ≥ 0.75 on normalised
  names, excluding exact matches).
- Behaviour: a near match and no exact match → `ask_customer=True` and read-back "Is this for Kerala Fancy, or a new
  customer?"; `add_line` whose `item_code` is in the catalogue but `catalog.match(name_as_spoken)` returns a
  different item → problem `"Item code GPT does not match 'women's pant'"`, line not added; unknown item problem
  becomes `"Unknown item: silk saree. Closest: …"` (up to 3 names).

- [ ] **Step 1: Failing tests:** `test_near_miss_customer_asks` ("Kerala Fancies" vs open "Kerala Fancy");
  `test_item_code_contradicting_name_is_problem`; `test_unknown_item_offers_closest`;
  `test_matching_code_and_name_still_added` (GPT + "girls pant").
- [ ] **Step 2: Run** → FAIL. **Step 3: Implement.** Note: `match(name)` returning None is not a contradiction (keep
  the code); only a different item is.
- [ ] **Step 4: Run** full suite → PASS. **Commit** `feat: guardrails for near-miss customers and contradicting item codes`.

### Task 3: Isolated sample sessions

**Files:**
- Modify: `app/api.py`, `app/main.py`, `app/static/app.js`
- Test: `tests/test_sample_api.py`

**Interfaces:**
- Produces: sample endpoints take header `X-Sample-Session: <uuid>` (the page creates one per tab); each session gets
  its own `PieceService` on an in-memory store (`Store(":memory:")`), kept in an LRU of 200 sessions. Sample never
  touches the live database. `GET /api/orders` takes optional `X-Sample-Session` to list that session's orders.

- [ ] **Step 1: Failing tests:** `test_two_sample_sessions_are_independent` (session A finishes; session B's
  `next` returns index 1); `test_sample_reset_does_not_touch_live_orders` (save a live order, reset a sample session,
  live order still listed without the header).
- [ ] **Step 2-4:** run → FAIL; implement; full suite → PASS.
- [ ] **Step 5: Commit** `fix: sample runs in its own session store`.

### Task 4: Provider protocols, tracing and cost

**Files:**
- Create: `app/providers/__init__.py`, `app/providers/base.py`, `app/providers/costs.py`, `app/obs/__init__.py`,
  `app/obs/trace.py`
- Modify: `app/store/db.py` (traces columns: `piece_id, span, provider, ms, cost_paise, ok, error, meta_json`)
- Test: `tests/test_trace.py`

**Interfaces:**
- Produces: `Transcript(text: str, language: str, seconds_audio: float)`;
  `class SpeechToText(Protocol): def transcribe(self, wav_path: Path) -> Transcript`;
  `class Extractor(Protocol): def extract(self, transcript: str, open_orders: list[Order], catalog: Catalog) -> ExtractResult`
  with `ExtractResult(result: PieceResult, input_tokens: int, output_tokens: int, attempts: int)`;
  `class TextToSpeech(Protocol): def speak(self, text: str, language: str) -> bytes` (WAV);
  `ProviderError(Exception)` (message safe to show); `costs.stt_paise(seconds: float) -> int`,
  `costs.chat_paise(inp: int, out: int) -> int`, `costs.tts_paise(chars: int) -> int` (all round up);
  `trace.span(store: Store, piece_id: int | None, name: str, provider: str)` context manager yielding a dict where the
  caller may set `cost_paise` and `meta`; records ms, ok, error text on exception (re-raises);
  `Store.traces_for(piece_id: int) -> list[dict]`.

- [ ] **Step 1: Failing tests:** `test_span_records_time_and_cost`; `test_span_records_error_and_reraises`;
  `test_costs_round_up` (`stt_paise(60) == 49`, `chat_paise(429, 531) == 2`, `tts_paise(1000) == 250`).
- [ ] **Step 2-4:** FAIL → implement → PASS. **Step 5: Commit** `feat: provider protocols, traces and cost estimates`.

### Task 5: Audio preparation and Sarvam speech-to-text

**Files:**
- Create: `app/audio.py`, `app/providers/sarvam_stt.py`, `tests/test_audio.py`, `tests/providers/__init__.py`,
  `tests/providers/test_sarvam_stt.py`, `tests/fixtures/audio/hello.wav` (1.5 s tone + silence, generated by the test
  helper with ffmpeg if absent)
- Modify: `requirements.txt` (`httpx==0.28.1`, `python-multipart==0.0.20`), `requirements-dev.txt`
  (`imageio-ffmpeg==0.6.0`), `.gitignore` (`!tests/fixtures/audio/*.wav`, `!app/sample/audio/*.wav`),
  `.github/workflows/ci.yml` (`sudo apt-get install -y ffmpeg` in the test job)

**Interfaces:**
- Produces: `audio.ffmpeg_exe() -> str` (`shutil.which("ffmpeg")`, else `imageio_ffmpeg.get_ffmpeg_exe()`);
  `audio.to_wav16k(src: Path, dst: Path) -> float` (mono 16 kHz, returns seconds; raises `AudioError` on undecodable);
  `audio.silences(wav: Path) -> list[tuple[float, float]]` (ffmpeg `silencedetect=noise=-35dB:d=0.35`);
  `audio.choose_cuts(duration: float, silences: list[tuple[float, float]], max_len: float = 28.0) -> list[float]`
  (pure: greedily cut at the midpoint of the last silence before each `max_len` boundary; hard cut at `max_len` when
  none); `audio.split(wav: Path, cuts: list[float], out_dir: Path) -> list[Path]`;
  `AudioError(Exception)`; `SarvamSTT(api_key: str, client: httpx.Client | None = None)` implementing
  `SpeechToText`, transcribing each chunk and joining with a space; language from the first chunk with a non-empty
  transcript.

- [ ] **Step 1: Failing tests:** `test_choose_cuts_prefers_silence` (`choose_cuts(35.8, [(17.6, 18.2)]) == [17.9]`);
  `test_choose_cuts_hard_cut_without_silence` (`choose_cuts(60, []) == [28.0, 56.0]`);
  `test_choose_cuts_short_audio` (`choose_cuts(12, []) == []`); `test_to_wav16k_rejects_garbage` (bytes `b"not audio"`
  → `AudioError`); `test_sarvam_stt_joins_chunks` (httpx `MockTransport` returning two transcripts; asserts form
  fields `model=saaras:v4`, `mode=codemix`, `language_code=unknown` and header `api-subscription-key`);
  `test_sarvam_stt_5xx_raises_provider_error`.
- [ ] **Step 2-4:** FAIL → implement → PASS.
- [ ] **Step 5: Real check (not in CI):** transcribe `data/private/recordings/2026-11-27-customer-order-1.ogg`
  through `SarvamSTT` with silence cuts; expect one transcript containing "Girnar Transport" with no duplicated
  "50 piece" at the cut. Record the result in the ledger.
- [ ] **Step 6: Commit** `feat: audio splitting at pauses and Sarvam speech-to-text`.

### Task 6: Sarvam extractor with validation, retry and prompt fixes

**Files:**
- Create: `app/providers/prompt.py`, `app/providers/sarvam_llm.py`, `app/providers/fixture.py`,
  `tests/providers/test_sarvam_llm.py`, `tests/providers/test_prompt.py`

**Interfaces:**
- Produces: `prompt.build_messages(transcript: str, open_orders: list[Order], catalog: Catalog) -> list[dict]`
  (system message: role and rules; item list as `CODE: name (aliases)`; open orders as
  `#id customer, city: CODE sizes…`; four worked examples as user/assistant pairs: (a) age bands go to `sizes`
  (`{"1-10 yrs": 50}`) with one `add_line` per item; (b) "book Girnar Transport, I'll pay to your account" →
  `set_field transport "Girnar Transport"` and `set_field payment "bank"`; (c) no shop name said → `customer: null`;
  (d) an item not in the list → `item_code: null`, keep `name_as_spoken`; rule text: "never use the code of a
  different item: women's and teen items are not girls' items");
  `SarvamExtractor(api_key: str, client: httpx.Client | None = None, model: str = "sarvam-105b")` implementing
  `Extractor`: one retry, sending the validation error back as a user message; second failure → `ProviderError`;
  `FixtureExtractor(results: list[PieceResult])` returning them in order.

- [ ] **Step 1: Failing tests:** `test_prompt_lists_open_orders_with_ids`; `test_prompt_has_age_band_example`;
  `test_extractor_valid_first_try` (MockTransport; `attempts == 1`, tokens read from `usage`);
  `test_extractor_retries_once_on_invalid_json` (`attempts == 2`; second request contains the error text);
  `test_extractor_gives_up_after_two_invalid` (`ProviderError`); `test_extractor_timeout_is_provider_error`;
  `test_request_body_uses_json_schema_strict` (`response_format.json_schema.strict is True`, `reasoning_effort is None`).
- [ ] **Step 2-4:** FAIL → implement → PASS.
- [ ] **Step 5: Real check (not in CI):** run on the Hindi transcript (scratch script). Expected now: customer null,
  GPT with sizes `{"1-10 yrs": 50}` only for girls; women's and teen items `item_code` null; transport and payment
  set. Ledger the actual output, good or bad.
- [ ] **Step 6: Commit** `feat: Sarvam extractor with strict schema, retry and worked examples`.

### Task 7: Live piece endpoint, upload and hold-to-talk

**Files:**
- Create: `app/flow/live.py`, `app/ratelimit.py`, `tests/test_live_api.py`
- Modify: `app/api.py`, `app/main.py`, `app/store/db.py` (piece state `failed`; `audio_path` set),
  `app/static/index.html`, `app/static/app.js`, `app/static/styles.css`

**Interfaces:**
- Consumes: Tasks 4-6 protocols; `PieceService.propose`.
- Produces: `LiveService(pieces: PieceService, stt: SpeechToText, extractor: Extractor, audio_dir: Path)` with
  `from_audio(upload_path: Path, original_name: str) -> LiveOutcome` and `from_text(text: str) -> LiveOutcome`;
  `LiveOutcome(proposal: Proposal | None, transcript: str, language: str, timings_ms: dict[str, int],
  cost_paise: int, error: str | None)`. HTTP: `POST /api/pieces/audio` (multipart `audio`) and `POST /api/pieces/text`
  (`{"text": str}`) → `{"transcript", "language", "timings_ms", "cost_paise", "cost", "proposal" | null, "error" | null}`;
  503 without key; 422 for `AudioError`; 429 from `RateLimiter(per_ip_hour=30, per_day=300)`.
  Failure message (exact): `Couldn't understand that. Please say it again, or type it.`
  `GET /api/pieces/{id}/audio` streams the stored audio (404 if none).
- UI: mic enabled when providers are ready (hold to record with `MediaRecorder`, `audio/webm`), "Upload a voice note"
  file input (`accept="audio/*"`), a text box "Or type the order"; the slip shows the transcript, "STT 1.8 s · AI 2.4 s ·
  ₹0.62 (estimated)", and a ▶ on each line that has a source piece with audio.

- [ ] **Step 1: Failing tests** (fakes for STT and extractor, no network): `test_audio_piece_proposes`;
  `test_text_piece_proposes`; `test_no_key_returns_503` (real providers, no env); `test_garbage_audio_422`;
  `test_provider_failure_sets_failed_state` (piece state `failed`, response `error` equals the exact message);
  `test_rate_limit_429`; `test_piece_audio_served`; `test_traces_written_per_step` (stt, extract spans).
- [ ] **Step 2-4:** FAIL → implement → PASS (full suite).
- [ ] **Step 5: Browser check** (Playwright, key set locally): upload the Hindi note → slip shows lines and timings;
  screenshot `docs/round2/screens/s3-live-hindi.png`.
- [ ] **Step 6: Commit** `feat: live voice pieces by upload, hold-to-talk or typing`.

### Task 8: Eval set v1 and scorer

**Files:**
- Create: `eval/__init__.py`, `eval/cases/*.json` (12 cases), `eval/score.py`, `eval/run.py`, `eval/README.md`,
  `docs/round2/05-evalset.md`, `tests/test_eval_score.py`

**Interfaces:**
- Case format: `{"id", "source": "real"|"synthetic", "language", "pieces": [{"transcript", "gold_customer":
  "new"|"#<n>"|"ask", "gold_changes": [Change JSON]}], "gold_final": [{"customer", "lines": [{"item_code", "sizes",
  "quantity"}], "transport", "payment"}]}`.
- Produces: `score.score_case(case: dict, run: CaseRun) -> CaseScore` and `score.summary(scores) -> dict` with
  `routing_acc, change_acc, final_order_acc, silent_errors, p50_ms, cost_paise_total`. A **silent error** is a final
  order line whose quantity, size or item differs from gold and was not flagged by a problem or ask.
  `python -m eval.run --provider fixture|sarvam --out eval/reports/` writes `YYYY-MM-DD-<provider>.md` and `.json`.
- Cases (12): the real Hindi note (transcript from discovery §6d) as `source: real`; 11 synthetic, labelled, covering:
  2-3 piece merges (Tamil code-mix), a change and a removal, a near-miss customer, a forwarded note with no shop name,
  an unknown item, a rate spoken off-list, transport+payment only, Malayalam-English, Kannada-English, an "unclear"
  piece.

- [ ] **Step 1: Failing tests:** `test_perfect_run_scores_100`; `test_wrong_quantity_unflagged_is_silent_error`;
  `test_wrong_quantity_flagged_is_not_silent`; `test_routing_counts_ask_as_correct_when_gold_is_ask`.
- [ ] **Step 2-4:** FAIL → implement → PASS.
- [ ] **Step 5: Run** `python -m eval.run --provider sarvam` (key set). Commit the report as is, whatever it shows;
  write the numbers and one paragraph of failure analysis into `05-evalset.md` and the README.
- [ ] **Step 6: Commit** `feat: eval set v1 with scorer and first Sarvam report`.

### Task 9: Spoken read-back, voice confirm and sample audio

**Files:**
- Create: `app/flow/reply.py`, `app/providers/sarvam_tts.py`, `scripts/make_sample_audio.py`,
  `app/sample/audio/piece1.wav` … `piece3.wav`, `tests/flow/test_reply.py`, `tests/providers/test_sarvam_tts.py`
- Modify: `app/flow/readback.py`, `app/api.py`, `app/static/app.js`, `app/sample/conversation.json`

**Interfaces:**
- Produces: `readback.build_readback(..., language: str = "en-IN")` with `ta-IN` and `hi-IN` templates (same
  structure: who, each change, total, still needed, "say sari / haan to confirm"); `reply.classify(text: str) ->
  Literal["yes","no","other"]` using the Global Constraints word lists on normalised text (whole words; "ok" inside
  "book" must not count); `SarvamTTS(api_key, client=None)`; `POST /api/pieces/{id}/speak` → `audio/wav` (503 without
  key; the page falls back to `speechSynthesis`); `POST /api/pieces/{id}/reply` (multipart audio) → transcribe →
  `yes` confirms, `no` discards, `other` runs the audio as a new piece and leaves this one pending.
- Sample audio: `scripts/make_sample_audio.py` calls Bulbul for the three sample transcripts; the sample bubble gets a ▶
  and the label `Sample: saved AI results · synthetic voice`.

- [ ] **Step 1: Failing tests:** `test_classify_yes_tamil` ("சரி" → yes); `test_classify_haan`;
  `test_classify_no_vendaam`; `test_classify_other_new_order_text` ("also add ten shorts" → other);
  `test_classify_ok_inside_word_is_not_yes` ("book it" → other); `test_readback_tamil_piece1` (Tamil read-back
  of sample piece 1 contains "₹3,131.10" and "சரி"); `test_reply_other_keeps_piece_pending`;
  `test_tts_request_body` (MockTransport: `target_language_code`, `model=bulbul:v3`).
- [ ] **Step 2-4:** FAIL → implement → PASS.
- [ ] **Step 5:** Generate the sample WAVs (key set), commit them; ask the owner to check the Tamil read-back wording.
- [ ] **Step 6: Commit** `feat: spoken read-back in Tamil and Hindi with voice confirm`.

### Task 10: Docs, status page and halfway gate

**Files:**
- Modify: `README.md` (status table, eval table, screenshot), `docs/round2/04-rfc.md` §12 (actual dates),
  `docs/round2/project-status.html` (artifact source)

- [ ] **Step 1:** Halfway gate, by hand with the key set: upload the real Hindi note → read-back spoken → say "haan"
  → order saved with transport and payment; screenshot. Record pass or fail honestly in the ledger.
- [ ] **Step 2:** Update README "What works today / Planned" and the eval table from Task 8's report.
- [ ] **Step 3:** Run `python -m pytest -q` → PASS; push branch; CI green.
- [ ] **Step 4: Commit** `docs: S2-S4 status, eval results and halfway gate`.

---

## Self-review notes

- Spec coverage: R1 (T7), R2 (T5), R3 (T6), R5 (T7 slip), R6 (T9), R7 voice (T9), R11 playback (T7), R14 traces
  (T4, T7; full `/traces` page cut), eval §9 (T8), guardrails 3-5 (T2, T7). R9-R10 (bill, khata) belong to the S5 plan.
- Cut on purpose (review): `/traces` page, Gemini backup extractor, fpdf2 PDF, S6 extras, Tamil labels.
- Probe findings 1-4 each have a test: 1 → T1 `test_customer_not_said_asks` + T6 example (c); 2 → T2
  `test_item_code_contradicting_name_is_problem`; 3 → T6 example (a) + eval real case; 4 → T6 example (b) + eval.
- Open dependency: women's/teen item rates from the owner. Until then the real Hindi case's gold marks those items
  as "unknown item asked", which is the correct guarded behaviour.
