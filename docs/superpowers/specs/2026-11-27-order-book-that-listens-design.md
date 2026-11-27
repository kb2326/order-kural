# Order Kural: "the shop's order book that listens" (design, 2026-11-27)

**Status:** the owner approved the direction on 27 Nov, with two changes: tax calculation is out of scope, and the
khata moves into the app. This doc extends `docs/round2/04-rfc.md` and the S2-S4 plan; it does not replace them.

## 1. Intent: why we are building this

The user is a Khaderpet (Tirupur) garment wholesaler. Orders arrive in many ways:
- calls;
- forwarded WhatsApp voice notes;
- walk-ins;
- referrals.

Buyers speak Tamil, Hindi, Malayalam or Kannada, and an order often comes **in pieces**, over hours or days.

He keeps it all in several places:
- **Book 1:** customers;
- **Book 2:** order details;
- **the Khatabook app:** credit;
- **nothing for stock;**
- **his auditor** does GST monthly.

**Why not just ChatGPT** (his own question): a chat tool forgets. It doesn't know his customers or his open orders. It
doesn't merge the 4th voice note into the order from the 1st, and it keeps no money ledger. Order Kural is his order
book and khata, and he fills and queries it by voice.

**The rule that decides adoption:** each order must cost him **fewer actions than writing in two notebooks**, and
must give him something back at once.

## 2. Goals, non-goals and anti-goals

**Goals (the one core flow, end to end, by voice):**

1. An order comes in by forwarding or uploading a voice note, by speaking (mic), or by typing.
2. The AI turns each piece into a change list.
3. The code applies it to the customer's open order. Book 1 and Book 2 are filled automatically.
4. The app reads the order back in the buyer's language. The owner says **"sari"** (or "haan", "seri", "howdu",
   "ok").
5. Then **"bill it"** (by voice or tap) makes a **numbered bill** and a **packing list**, both shareable. The bill
   total is added to the buyer's **khata** as money owed.
6. **"Kerala Fancy paid 10,000 by UPI"** adds a payment to the khata.
7. **Ask the shop** by voice, and hear the answer spoken. There are exactly three questions:
   - "What is still to ship?"
   - "What did/does <customer> order/owe?"
   - "How many <item> were ordered this week?"

**Non-goals (for this round):**
- **Tax and GST calculation:** the auditor does it monthly. The bill shows line amounts and a total, with HSN codes
  and no tax maths.
- Stock and goods-in tracking.
- A WhatsApp integration or bot.
- Logins and multiple shops.
- Reminders sent to buyers.
- Open-ended chat questions.

**Anti-goals (a failure even if it "works"):**
- The AI invents a customer, item, quantity or rupee figure. Code checks everything; when unsure, the app asks.
- Anything is saved without the owner's confirmation.
- The app won't start without keys, or the demo needs a key.
- An order takes him more steps than the notebook does.

## 3. Constraints

- Round 2 rules (`docs/round2/requirements.md`):
  - a public repo where `docker compose up` works **with no keys**;
  - a video of 3 minutes or less;
  - a deck written as text;
  - an optional live link;
  - due 30 Nov, 11:59 pm.
- No agent frameworks (LangGraph, ADK); no WhatsApp API.
- Sarvam only for speech and the LLM, with the key in `.env`, never printed.
- Money stays in integer paise; rules stay in code (ADR-005).
- A buyer's real voice notes stay in `data/private/` and are never committed.

## 4. Approaches considered

| Approach | Trade-off | Verdict |
|---|---|---|
| **A. Order → bill and packing list as the core, plus khata and a 3-question "Ask"** | Gives value on the first order. "Ask" and khata show why the data is worth collecting. More slices to build | **Chosen** (owner approved 27 Nov) |
| B. A "voice note → saved record" logger only | Cheapest, but gives nothing back. Fails the "why not ChatGPT" test | Dropped |
| C. Open "chat with your shop" (the LLM writes SQL or answers freely) | Impressive in a demo, but it can't be tested and it can make figures up. Breaks the anti-goal | Dropped. "Ask" is 3 fixed questions answered by code |
| D. Keep Khatabook separate (the bill just says "credit") | Less to build, but the pipeline stays broken in two. The owner wants one place | Dropped by the owner: the khata comes in-app |

## 5. Architecture

**Principle: "AI proposes, code decides, the owner confirms."** The AI only turns speech into a *change list*. Plain,
tested code does every match, check, sum and save, and nothing is saved until the owner says "sari".

```
Phone browser (one page, no build step)
  mic / upload / type ──► POST /api/pieces/audio|text
                                  │
            ┌─────────────────────┼───────────────────────────── one "piece" ───┐
            │ 1 audio prep   ffmpeg → 16 kHz WAV, cut at pauses ≤ 28 s (ADR-004) │
            │ 2 listen       Sarvam Saaras v4 (codemix) → transcript + language  │
            │ 3 understand   Sarvam-105b, strict JSON schema → PieceResult        │
            │                intent: order_changes | bill_order | mark_shipped |  │
            │                        record_payment | ask | unclear               │
            │ 4 check        guardrails: customer match / near-miss ask,          │
            │                item code plausible, sizes, unknown → closest        │
            │ 5 decide       domain code (pure): apply changes / build bill /     │
            │                ledger entry / answer query  → proposal + read-back  │
            │ 6 speak        Sarvam Bulbul v3 in the piece's language             │
            └─────────────────────────────────────────────────────────────────────┘
                                  │
  slip on screen + audio ◄────────┘     owner: "sari" (word list, no AI) / "no" / edit
                                  │
                         confirm ─► SQLite transaction (claim piece, re-apply, save)
```

**The parts (existing, or added by this design):**

| Part | Where | Job |
|---|---|---|
| Front end | `app/static/` | Mic (hold to talk), upload, type, the slip, read-back audio, bill and packing-list view, khata view, Ask button |
| API | `app/api.py` | Thin HTTP layer; per-tab sample sessions; 503 "key not set", 422 bad audio, 429 rate limit |
| Providers | `app/providers/` | `SpeechToText`, `Extractor`, `TextToSpeech` protocols. Sarvam versions, plus fixture versions for the keyless sample and tests. Swapping vendors means changing one file |
| Audio | `app/audio.py` | Convert and split at pauses |
| Flow | `app/flow/pieces.py` | The piece state machine: transcribed → proposed/read_back → applied/discarded. Customer routing |
| Domain | `app/domain/` | Catalogue, order engine, rules (minimums, flags), money. **New:** `bill.py` (numbered bill and packing list), `khata.py` (ledger: bill = debit, payment = credit, balance), `queries.py` (the 3 Ask questions) |
| Store | `app/store/db.py` | SQLite: customers, orders, lines, pieces, events, traces. **New:** `bills`, `ledger_entries` |
| Observability | `app/obs/trace.py` | Time and estimated cost per step, per piece, shown on the slip |
| Eval | `eval/` | Real-style pieces with the right answers. A scorer for fields and numbers, per language |

**The intents and what code does with each:**

| Intent (what was said) | Code action | Read-back |
|---|---|---|
| `order_changes` ("Kerala Fancy, 24 palazzo…") | apply to the open order, or create one | the changed lines and the order so far |
| `bill_order` ("bill it") | freeze the lines into bill no. N, make the packing list, add a khata debit for the total | "Bill 12, ₹26,552" |
| `record_payment` ("paid 10,000 UPI") | khata credit entry, which needs a customer and an amount | "₹10,000 received; balance ₹16,552" |
| `mark_shipped` ("sent by KPN") | set the order to shipped and record the transport | "Marked shipped" |
| `ask` (3 kinds) | answer from a code query; **no AI makes up the answer** | the answer, spoken |
| `unclear` | nothing | "Please say it again, or type it" |

Every intent that writes data needs **"sari"**. `ask` doesn't write, so it answers straight away.

### 5b. The live path is a real-time voice agent (owner approved 27 Nov, after the spike)

The batch pipeline above stays for **uploaded voice notes**. **Live talk** is a real-time voice agent built with
**Pipecat**, which is a real-time audio pipeline framework and not an agent-orchestration framework. It is mounted in
our FastAPI app on a WebSocket, so it runs on Cloud Run in one container with no WebRTC or UDP.

- **Agent type: a single tool-using conversational agent, bounded, with a human approving every change.**
  - One LLM (sarvam-105b, `reasoning_effort="none"`).
  - About 10 fixed tools.
  - Short-term memory is the conversation; long-term memory is SQLite, reached only through tools.
- **Pipeline:**
  1. browser mic (PCM16 16 kHz over a WebSocket);
  2. `SarvamRealtimeSTTService` (saaras:v4, codemix; server-side VAD and endpointing);
  3. user aggregator (External turn strategies; barge-in on);
  4. `SarvamLLMService` with the tools;
  5. `SarvamTTSService` (bulbul, in the owner's language);
  6. audio back to the browser.

  Order-slip events are sent to the page on the same socket.
- **Tools:**
  - **read tools**, which never need "sari": `find_customer`, `get_open_order`, `ask_shop`;
  - **write tools**, which only *stage* a change: `add_to_order`, `change_line`, `remove_line`, `set_detail`,
    `bill_order`, `record_payment`, `mark_shipped`;
  - **approval tools:** `confirm_pending` saves staged changes in one transaction, idempotently, via `claim_piece`.
    It is registered with `cancel_on_interruption=False`. `discard_pending` drops them.

  Tools reuse the domain and guardrails (catalogue plausibility, customer near-match, quantity rules).
- **Grounded replies (a rule; spike finding).** Every tool returns `facts` plus a `say` sentence built by code. The
  agent speaks `say`, and may add one short question. It must never describe an order change that no tool returned.
  The eval measures **claims versus tool calls** per turn.
- **The spike (27 Nov), with synthetic Tamil and Hindi speech:**
  - Latency passed: the first reply text came 0.35-0.9 s after the end of speech, and TTS first audio about 0.7 s
    after that.
  - Pipecat and FastAPI worked together in one process.
  - It called `add_to_order` correctly from Tamil: Kerala Fancy, PPL, S/M/L/XL 6 each.
  - It called `confirm_order` on "சரி".
  - It asked instead of guessing when STT garbled "crop top M 10 L 10 KPN".
  - **Failure:** once it *said* "added, payment credit, total ₹1,560" without calling any tool. The grounded-replies
    rule above exists because of this.
- **Checked against standard designs:**
  - OpenAI's voice-agent guide recommends a chained (STT → LLM → TTS) pipeline for approval-heavy flows with
    deterministic logic between stages.
  - Anthropic's "Building effective agents" recommends an augmented LLM (tools plus memory), starting simple, with
    programmatic checks.
  - Voice tool-calling guides (Soniox, Microsoft Agent Framework's tool approval) recommend splitting tools into
    lookup and action, confirming action tools, keeping them idempotent, validating arguments in code and reading
    critical details back.
  - Pipecat Flows (staged node graphs) is not needed yet, because the conversation has no fixed stages. Revisit if
    the tool set grows.

**Keyless and fallback paths:**
- **No key:** the sample runs on saved AI results and pre-made audio. The live buttons show "key not set".
- **Sarvam down or too costly:** the protocols let us switch to another speech-to-text, LLM or text-to-speech
  service. The domain, bill and khata keep working because they're plain code. Typing always works.

## 6. Decided by the owner

- One core flow: order → bill and packing list. Then khata and Ask as the payoff.
- Four languages: Tamil, Hindi, Malayalam, Kannada.
- **No tax maths** (the auditor's job). The bill can still be generated.
- The khata lives inside the app, not in Khatabook.
- No WhatsApp API and no agent frameworks.

## 7. My calls (the owner can correct these)

- **GST is hidden.**
  - The bill and the slip show quantity × rate = amount, the total and the HSN codes.
  - The existing GST code stays tested but is not shown, so it can come back later.
- **Bill numbers** run 1, 2, 3… per shop. A billed order is locked; later changes start a new order.
- **The khata starts at zero** for each customer. Opening balances can be added by voice later (non-goal now).
- **Ask** handles only the 3 question kinds. Anything else gets "I can answer: what is to ship, a customer's order or
  balance, item counts".
- **Read-back** is built from templates in code, per language, not written by the LLM. The numbers are always exact.
- **Cut order if we run late:**
  1. WhatsApp share button;
  2. Malayalam and Kannada read-back (fall back to Tamil);
  3. Ask;
  4. mark shipped.

  Bill, packing list and khata stay.

### Settled after the builder check (all my calls; the owner can correct them)

1. **Billing is one step, not a form.**
   - "Bill it" needs a customer and at least one line. Transport and payment are optional; when missing, they show
     as "not set" on the bill.
   - This relaxes the RFC's stricter gate, because a multi-question form breaks the effort rule.
2. **One "sari" per piece.**
   - It confirms the whole change list of that piece.
   - "Bill it" reads back "Bill 12, ₹26,552. Sari?" and one "sari" issues the bill.
   - Asking needs no "sari".
3. **Mistakes are fixed by reversal, never by deleting.**
   - The khata is append-only. A tap-only **Undo** on the latest bill or payment adds a reversal entry; for a bill,
     it also unlocks the order.
   - There is no voice undo, which avoids accidental cancels.
4. **Tables are added, not migrated.**
   - New tables `bills` and `ledger_entries` are added; the RFC's planned `khata_entries` is replaced by
     `ledger_entries`.
   - The bill is an **order bill or estimate, not a GST tax invoice**. It says "Tax as per final invoice", so the
     GST invoice fields (CGST Rule 46) are not in this round.
   - The existing S0-S1 tables are unchanged.
5. **How Ask resolves its words:**
   - "this week" means the last 7 days;
   - the customer uses the same matcher as orders, and asks when the match is ambiguous;
   - the item uses `catalog.match`;
   - unknown words get the "I can answer…" message.
6. **Demo languages:** Tamil for the owner's own voice and Hindi for a forwarded buyer note.
   - The keyless sample's fixtures and pre-made audio cover these two.
   - Malayalam and Kannada are covered live and in the eval only.
7. **The keyless sample tells the whole story:**
   - the order pieces;
   - "sari";
   - "bill it", which makes the bill, the packing list and the khata debit;
   - one payment;
   - one Ask.

### Changed 27 Nov evening: real GST tax invoices (owner approved)

The owner shared a real GST tax invoice and an unofficial "estimate". Under CGST Act s.31 and Rule 46, a registered
supplier must issue a tax invoice for every taxable supply, and selling without one is an offence under s.122. So:

- **"Bill it" makes a GST tax invoice** in the shop's own paper layout.
  - Invoice number series per financial year (`KG/26-27/0001`).
  - Seller and buyer GSTINs, place of supply, HSN, size, quantity, rate and amount.
  - 5% / 18% per piece (Rs 2,500 threshold); **IGST** for another state, **CGST + SGST** inside Tamil Nadu.
  - Round-off to the rupee, the amount in words, bank details, terms and signatory.
  - **B2C** invoices for buyers without a GSTIN.
- **The place of supply comes from** the buyer's GSTIN, a stated state, or a known town. If none is known, the agent
  asks for it and never guesses.
- **The khata is debited with the grand total.**
- **Monthly auditor report:** `GET /api/reports/gst.csv?month=YYYY-MM`, one row per invoice, voided invoices left out.
- **Unofficial estimates are out of scope:** the product never offers a document that replaces a tax invoice.
- **Shop details** (`data/shop.json`) are made up for the demo. The real bills stay in `data/private/`.

This supersedes the "no tax maths" non-goal and the "order bill (estimate)" decision above.

## 8. Left to the builder

- Exact page layout of the bill and packing list. ADR-007 sets the bill format: printable HTML, plus share text.
- The prompt wording for the new intents. Every new intent gets at least one worked example and eval cases.
