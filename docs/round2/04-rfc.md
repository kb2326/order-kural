# 04 · RFC: Order Kural prototype design (v2, 2026-11-27)

**v2 changes (to match PRD v2):** orders are assembled from many voice pieces; the AI returns a *change list* against
open orders; data model follows Tally's record chain; stock removed; slices re-planned with "one working path by the
halfway mark".

**What an RFC is for:** "Request for Comments". It explains *how* we will build what the PRD asks for, so the team
can spot problems before code exists. Big choices get their own short decision record (ADR) in `adr/`.

**Inputs:** `03-prd.md` (what and why), `requirements.md` (competition rules). **Status:** draft for the owner's
review.

---

## 1. Competition compliance first (every rule mapped to a design decision)

The organisers gave no scoring rubric, so **every written rule is treated as a hard requirement**. This table is the
checklist for the launch gate.

### 1a. Code on GitHub

| Rule (exact wording, shortened) | How the design meets it | Checked by |
|---|---|---|
| "Keep your GitHub project public" | Repo `kb2326/order-kural`, public from the first push | Open the URL in a private browser window |
| "Add a Docker setup file (docker-compose.yml). It lets us start your app with one command" | `docker-compose.yml` at the repo root; `docker compose up` builds and starts one service on port 8000; no other step needed; `.env` is optional | CI job runs `docker compose up` and calls `/health`; fresh-clone test on the friend's laptop |
| "Your app must start and show its main screen without any secret keys… it can show a 'key not set' message" | Every provider reads its key at request time, never at startup. Missing key → provider status "not set" → banner on the main screen and a "key not set" message on the affected button. **A "Try a sample order" button runs the full flow with no keys** (ADR-006) | CI starts the container with **no** environment variables and loads `/`; a test asserts the banner text |
| "Write your own code during the hackathon, about 300 lines or more. A starter template with only small changes will not pass" | No template. Every file is written from 27 Nov. The rules engine, flow state machine, providers, eval runner and UI are all ours (expected 1,500+ lines). Git history shows the work by day | `git log` dates; a line count in the README |
| "If it does not start, your build cannot move ahead" / "ask a friend to download your code from GitHub and start it" | README "Run it" section with three commands; Docker image built from pinned versions | Friend's fresh-clone test on 29 Nov |

### 1b. Demo video

| Rule | Plan |
|---|---|
| YouTube, "public or unlisted" | Upload as **unlisted** |
| "3 minutes or less" | Script targets 2:30 (see the ship plan, slice 8) |
| "Show your product working" | Screen and phone recording of a real Tamil voice order going end to end; no mock-ups |

### 1c. Pitch deck (PDF). **"We read the words in your deck, not the pictures"**

Every point is written as text on the slide, not inside images. Each required topic gets its own slide, titled with
the organisers' own words so a reader (human or AI) finds it immediately:

| Required topic (organisers' words) | Slide title | Source in our docs |
|---|---|---|
| "Problem and solution: who has the problem and how your product solves it" | **Problem and solution** | PRD §1, §3, §4 |
| "Who it is for: who your users are and how many of them there could be" | **Who it is for** | PRD §2; market scan §3 |
| "What it depends on: the voice tools, AI models or other services you use, and what happens if they get costly or stop working" | **What it depends on** | RFC §6; PRD §9 |
| "Launch plan: how you will reach your first users and grow" | **Launch plan** | To write on 29 Nov |

### 1d. Live link (optional)

Small bonus if it works; it must stay up until 2 Dec. Plan: deploy the same Docker image to Google Cloud Run (project
already exists on the personal account), with a daily cost cap (ADR-008, decided on 29 Nov).

### 1e. The brief itself

| Brief line | Design answer |
|---|---|
| "The main task in your product is done by speaking" | Ordering, answering missing details, confirming and correcting are all spoken. Taps exist only as a backup |
| "Something people in India do today by typing, tapping or filling forms" | Today: handwritten notebook, then a typed bill, then a khata entry. Order Kural replaces all three with speech |
| "One core flow that works end to end. Not a full product" | Exactly the PRD §4 flow; everything else is out of scope |
| Theme | Livelihoods and small business |
| Form fields | Extension of the Round 1 idea; project name "Order Kural"; state Tamil Nadu |

### 1f. "Build by voice" (theme, no proof required)

The owner dictates prompts, documents and commit messages with **Wispr Flow**. We keep a short log
(`docs/round2/built-by-voice.md`) and show 10 seconds of it in the video. See §7 for Wispr's role in the product.

## 2. Architecture

```
 Phone or laptop browser (one page, WhatsApp-style)
   │  hold-to-talk (MediaRecorder, WebM/Opus) · upload voice note · tap backups
   ▼
 FastAPI app (one Docker container, Python 3.12)
   ├── api/            HTTP routes: /api/orders, /api/orders/{id}/audio, /reply, /confirm, /bill, /khata,
   │                   /api/status (which keys are set), /api/sample, /traces, /health
   ├── flow/           order state machine (§3)  ◄── the heart of the app
   ├── domain/         pure Python, no network: price list, item matching, minimum quantities, GST, totals,
   │                   missing-field detection, voice intent rules (yes / no / cancel / edit)
   ├── providers/      one interface per job, swappable:
   │     stt.py        SarvamSTT · (WisprSTT, only if API access is granted) · FixtureSTT (sample / tests)
   │     extract.py    SarvamExtractor (sarvam-105b, JSON schema) · GeminiExtractor (optional) · FixtureExtractor
   │     tts.py        SarvamTTS (bulbul) · none → browser speech fallback
   ├── audio/          ffmpeg: convert to 16 kHz mono WAV; split long audio at pauses into ≤ 28 s pieces
   ├── bills/          bill HTML (print) and PDF (fpdf2)
   ├── obs/            trace IDs, spans, cost estimates, JSON logs
   └── store/          SQLite (one file in a Docker volume)
 eval/                 eval set + runner (offline, from the command line)
```

**Why one container and no build step for the front end:** the judges run `docker compose up` once. Fewer moving
parts means fewer ways to fail (ADR-002).

## 3. Two state machines: the voice piece and the order

A state machine means something is always in exactly one named state, and only listed moves are allowed. It stops
the AI from skipping the confirmation step. There are two: one for **each voice piece** (short-lived) and one for
**each order** (lives for days).

**A voice piece:**

```
 RECEIVED ─convert/split─► TRANSCRIBED ─AI─► PROPOSED (customer + change list)
                                                │ our code checks the changes
                                                ▼
                                            READ_BACK (only the change + new total; asks if something is missing
                                                │                       or the customer is unclear)
                     "sari" / tap ✔ ────────────┼──────────── "vendaam" / tap ✖
                                                ▼                              ▼
                                            APPLIED (order updated)        DISCARDED
```

**An order** (Tally's equivalent in brackets):

```
 OPEN (pending sales order) ──"bill it" + confirm──► BILLED (invoice + khata) ──mark shipped──► SHIPPED (delivered)
      ▲    │ each APPLIED piece changes it                                         
      └────┘                                    "cancel order" + confirm (only while OPEN) ──► CANCELLED
```

**Rules that make it safe** (PRD guardrails):
- An order changes **only** when a piece reaches `APPLIED`, which needs the owner's confirmation.
- Only `OPEN` orders accept changes; a piece for a `BILLED` customer starts a **new** order (and says so).
- "Bill it" needs no missing required fields (customer, at least one line, transport, payment); otherwise the app
  asks for them first.
- Every applied change is stored as an **event** (who said what, when, which audio), so the order can be explained
  and replayed line by line.

## 4. Key designs

### 4.1 Long voice notes (PRD R2; ADR-004)

Sarvam's quick speech-to-text call accepts at most 30 s. Steps:
1. ffmpeg converts any input (WebM, Ogg/Opus, M4A, MP3, WAV) to 16 kHz mono WAV.
2. If it is longer than 28 s, ffmpeg's silence detector finds pauses; we cut at the pause nearest each 28 s mark
   (a hard cut at 28 s if there is no pause), so words are not chopped.
3. Pieces are transcribed in parallel (Sarvam allows 60 requests a minute) and joined in order.
4. Fallback if quality suffers: Sarvam's batch API (up to 2 hours, but slower and asynchronous).

### 4.2 Speech-to-text request (Sarvam Saaras v4)

`model="saaras:v4"`, `mode="codemix"` (English trade words stay in English, Tamil stays in Tamil script),
`language_code="unknown"` (auto-detect; never ask the owner to pick a language), `keyterms` = up to 50 terms built
from the price list (item names, sizes, transport names) to improve recognition. The response gives `transcript`,
`language_code` and `language_probability`. **No word-level confidence is returned**, so "unclear" highlighting
comes from the extraction step and the rules (PRD R5), not from the speech model.

### 4.3 Understanding a piece (transcript + memory → customer + change list)

This is the core AI step and the reason the product isn't "ChatGPT with a bill".

- **Input to the AI:** the transcript; a compact list of **open orders** (id, customer, city, lines with item codes
  and quantities); the **item list** (code, name, aliases); the number words for each language ("rendu" = 2,
  "darjan" / "dozen" = 12, "ovvonnum" = each).
- **Output (strict JSON schema** via Sarvam chat `response_format` type `json_schema`, `strict: true`):
  - `intent`: `order_changes` | `bill_order` | `mark_shipped` | `record_payment` | `unclear`
  - `customer`: {`name_as_spoken`, `city`, `match`: open order id or `new`, `confidence`: high | low}
  - `changes[]`: each one of `add_line` {item_code or `unknown`, `name_as_spoken`, `sizes` {size: qty},
    `quantity_total`, `rate_spoken`}, `change_line` {item_code, new sizes or quantity or rate}, `remove_line`
    {item_code}, `set_field` {`transport` | `payment` | `city`, value}
  - `amount` (for `record_payment` only, as spoken)
  - `uncertain[]`: anything the AI was unsure of
- **Prompt rules:** copy numbers only from the transcript; never compute totals; if the customer could match two open
  orders, set `confidence: low` (the app then asks).
- **Our code then:** validates with Pydantic; resolves item codes (fuzzy match as a backup); applies the changes to
  a *copy* of the order; runs the rules engine; builds the read-back. Invalid JSON → one retry with the error → still
  invalid → show the transcript with "could not understand, please say it again" (never a half-applied change).
- Reasoning off or low (`reasoning_effort`) for speed; `max_tokens` sized for 15 lines.

### 4.4 Rules engine (our code; PRD R4; ADR-005)

Pure functions with unit tests:
- **Item match:** spoken name → price-list item by normalised text and fuzzy similarity; below a threshold → the item
  is marked unknown and the app offers the 3 closest matches.
- **Rates:** spoken rate if given; else price-list rate. A spoken rate more than 10% from the list is flagged for
  read-back.
- **Minimum quantities:** kids' wear 10 per size; crop tops 6 per size; pants and palazzos 24; shorts 10 (to confirm
  with the brother-in-law). A breach is flagged and read back as a question.
- **Totals and GST:** line total = quantity × rate; GST 5% per piece up to ₹2,500, 18% above (checked per piece,
  per the Sep 2025 rates); integer paise arithmetic, no floating-point money.
- **Missing fields:** buyer, transport and payment are required before read-back.

### 4.5 Voice replies during read-back (confirm, cancel, answer)

1. Transcribe the reply (same STT).
2. **Rules first, no AI:** a word list for yes ("sari", "seri", "aamaa", "haan", "theek hai", "ok", "yes") and no
   ("vendaam", "venda", "cancel", "nahi", "illa"), in all four languages.
3. Anything else is treated as **a new piece** for the same order (for example the answer "KPN" to "Which
   transport?", or "no, make it 12"), so it goes through §4.3 again. This replaces a separate "edit by voice" feature.

### 4.6 Read-back (text-to-speech)

The read-back text is built by **our code from the checked order** (not written by the AI), in the detected language,
under Sarvam's 2,500-character limit. Sarvam Bulbul (`bulbul:v3` first; we test `v4-flash` for Malayalam) returns
base64 WAV. If text-to-speech fails or has no key, the browser's built-in speech voice reads it, and the order card is
always on screen.

### 4.7 Bill and khata

- Bill fields follow CGST Rule 46 (supplier name, address and GSTIN, invoice number and date, buyer, HSN, description,
  quantity, unit, taxable value, tax rate and amount, total, place of supply, signature line). Shop details come from
  a settings file with clearly fake demo values.
- The bill is an HTML page with print styles (Save as PDF) and a PDF made by `fpdf2`, which the phone's share sheet
  can send to WhatsApp (WhatsApp links cannot attach files).
- Khata: one entry per confirmed credit order; buyer balances; the "Remind" button builds a polite reminder in the
  buyer's language from a template and opens WhatsApp with the text pre-filled.

### 4.8 No-key sample mode (PRD R9; ADR-006)

The app ships with one **sample conversation**: three Tamil pieces with a made-up shop name, each with its saved
transcript and saved AI result. **Status 27 Nov:** the pieces have no audio yet; S4 adds synthetic audio made with
Sarvam Bulbul, labelled "synthetic voice". "Try the sample conversation" replays them through the **same** piece and
order state machines and rules engine (bill and khata from S5), so a judge without keys sees pieces merging into one
order. The screen labels it "Sample: saved AI results". With keys set, the same audio can go to the live providers.

## 5. Data model (SQLite)

Follows Tally's record chain (`00b-lifecycle.md`), so it can be exported later.

| Table | Key columns | Tally equivalent |
|---|---|---|
| `customers` | id, name, city, phone, language | Customer ledger |
| `items` | code, name, aliases, category, sizes, rate_paise, hsn, min_rule | Stock item master (no stock counts this round) |
| `orders` | id, customer_id, state (open / billed / shipped / cancelled), transport, payment, created_at | Sales order |
| `order_lines` | id, order_id, item_code, sizes_json, quantity, rate_paise, flags_json, **source_piece_id** | Sales order lines |
| `voice_pieces` | id, order_id, audio_path, transcript, language, state, ai_result_json, created_at | (new) |
| `order_events` | id, order_id, piece_id, change_json, applied_at | (new: audit trail) |
| `invoices` | id, number, order_id, date, subtotal_paise, gst_paise, total_paise | Sales invoice |
| `khata_entries` | id, customer_id, order_id, kind (credit / payment), amount_paise, created_at | Receipt + outstanding |
| `traces` | id, trace_id, piece_id, span, provider, model, ms, cost_paise, ok, error, created_at | (new) |

## 6. Dependencies, cost and fallbacks (feeds the deck slide "What it depends on")

| Dependency | Used for | Price (Sarvam, pay as you go, excl. GST) | If it gets costly or stops |
|---|---|---|---|
| Sarvam Saaras v4 | Speech → text | ₹0.49 per minute of audio | Interface swap to Google Speech or Gemini audio; long term, open-source AI4Bharat IndicConformer self-hosted; typing always works |
| Sarvam `sarvam-105b` | Transcript → order JSON; edit replies | ₹10 per 1M input, ₹25 per 1M output tokens (introductory to end of 2026) | Gemini Flash behind the same interface; the rules engine is ours and does not change |
| Sarvam Bulbul | Read-back voice | ₹3 (v3) or ₹2 (v4-flash) per 1,000 characters | Browser built-in voice; the order card is always shown |
| ffmpeg, SQLite, FastAPI, fpdf2 | Audio, storage, server, PDF | Free, open source | n/a |
| WhatsApp share links | Sending bill and reminder | Free | Any other app via the share sheet |

**Estimated cost per order:** a 60 s note ≈ ₹0.49; extraction ≈ 2,000 tokens ≈ ₹0.05; read-back ≈ 300 characters ≈
₹0.90 (v3). **About ₹1.5 per order**, so about ₹90 a month for one shop (60 orders). We measure the real figure from
the traces.

## 7. Where Wispr fits

| Use | Status |
|---|---|
| **Building by voice** (the hackathon theme): the owner dictates prompts, docs and commit messages with Wispr Flow | Doing; logged in `built-by-voice.md` |
| **Wispr Flow API as a speech-to-text provider** inside the product | **Not possible yet:** the API is "exclusive access", needing approval via enterprise@wisprflow.ai, and its docs do not list Tamil, Malayalam or Kannada. The STT interface makes it a drop-in later. We email Wispr today to ask for hackathon access and language support (ADR-001) |

## 8. Observability (PRD R11)

- Every request gets a `trace_id`; each step (convert, split, stt, extract, rules, tts, bill) records a **span**:
  duration in ms, provider, model, input size, estimated cost, ok or error.
- Spans go to stdout as JSON lines and to the `traces` table.
- A `/traces` page lists recent orders with their steps, slowest step and cost. This shows in the demo that we can see
  what happens inside the AI pipeline.
- The eval runner (below) writes its results with the same trace IDs, so a wrong answer can be traced back to the
  transcript or the extraction.

## 9. Evaluation plan (details in `05-evalset.md`)

- **Cases are conversations:** each has 1-4 pieces (in order) and a hand-checked "gold" result per piece (customer
  routing + change list) and for the final order. (a) Text conversations now: ~15 written in Tamil, Malayalam, Hindi
  and Kannada (code-mixed), including tricky ones (two customers with similar names; "make it 12"; removing a line;
  a piece after billing); (b) audio conversations when the brother-in-law's recordings arrive.
- **Metrics:** item recall, quantity and size accuracy, header accuracy, silent error rate, latency, cost (PRD §7).
- **Runner:** `python -m eval.run --set text|audio` prints a table and saves a dated report in `eval/reports/`.
  Every prompt change is re-run, so we see whether it helped.
- Private audio stays out of git (`data/private/`, already ignored).

## 10. Testing and CI

- **Unit tests (pytest):** the rules engine, the state machine, intent rules, JSON validation, audio splitting points.
  Written **before** the code (test-driven).
- **Integration test:** the full sample flow with fixture providers (no network, no keys).
- **GitHub Actions on every push:** run pytest; build the Docker image; start it with no keys; check `/health` and that
  `/` shows the "key not set" banner. This is our automatic guard for the "starts without keys" rule.

## 11. Security and privacy

- Keys only in environment variables (`.env` locally, Cloud Run secrets on the live link); `.env.example` in the repo
  with empty values.
- Voice notes are not stored after processing unless the owner keeps them; private recordings never go to git.
- The live link is public, so: request size limits (10 MB), audio length limit (3 min), and a simple per-IP rate limit
  to protect our Sarvam credit.

## 12. Build slices (each slice works end to end before the next starts)

**Rule from hackathon judges: get one end-to-end path working by the halfway mark (28 Nov midday), then improve it.**

| Slice | Result you can see | When |
|---|---|---|
| **S0 Skeleton** | Public repo; `docker compose up` shows the main screen with the "key not set" banner; CI green | 27 Nov |
| **S1 Rules + order engine (no AI)** | Item list seeded; change lists applied to orders by code; totals, GST, minimums; unit tests; sample conversation runs on fixtures with no keys | 27 Nov |
| **S2 Voice in** | Record or upload → transcript (Sarvam, long-audio split); traces recorded | 27-28 Nov |
| **S3 AI understanding + eval v1** | Transcript + open orders → customer + change list; text eval set (conversations) runs and reports | 28 Nov morning |
| **S4 Read-back + confirm** | Spoken read-back of the change; "sari" applies, "vendaam" drops. **Halfway gate: one live voice order works end to end** | 28 Nov midday |
| **S5 Bill + khata** | "Bill it" → GST bill (print); khata entry and page; source audio playback per line | 28 Nov |
| **S6 Supporting** | Orders board; to-ship and mark shipped; payment + reminder link; missing-field question | 29 Nov |
| **S7 Observability + audio eval** | `/traces` page; eval on the brother-in-law's recordings | 29 Nov |
| **S8 Ship** | Live link; fresh-clone test; video (≤ 3 min); deck PDF; submit **by 30 Nov evening** | 29-30 Nov |

**Cut line if time runs out:** S6 items go first (taps remain), then the live link. S0-S5 are never cut.

### Demo video plan (≤ 3 min, from judging advice)

| Time | Content |
|---|---|
| 0:00-0:25 | The pain: "the order lives everywhere" (notebooks, voice notes); who he is |
| 0:25-2:05 | One live flow: 3 pieces from Kerala Fancy merge into one order → read-backs in Tamil → "bill it" → bill, khata, to-ship → tap a line, hear the original voice |
| 2:05-2:40 | How it works: AI reads, code calculates; eval results; `/traces` |
| 2:40-3:00 | Built by voice with Wispr Flow; "listens like ChatGPT, remembers like Tally" |

## 13. Decisions recorded as ADRs (in `docs/round2/adr/`)

| ADR | Decision |
|---|---|
| 001 | Sarvam for speech-to-text, extraction and voice, behind swappable interfaces; Wispr API later if access is granted; Gemini as the backup extractor |
| 002 | One Python FastAPI container with a plain HTML and JS front end (no build step) |
| 003 | SQLite in a Docker volume |
| 004 | Split long audio at pauses into pieces under 28 s |
| 005 | Prices, rules and totals in our code, never the AI |
| 006 | A no-key sample mode using recorded fixtures through the real pipeline |
| 007 | Bill as print HTML plus an fpdf2 PDF, shared via the phone's share sheet |
| 008 | Live-link hosting (decide on 29 Nov: Cloud Run vs another host) |

## 14. Risks

| Risk | Effect | Plan |
|---|---|---|
| Tamil numbers misheard | Wrong order | Keyterms; read-back; eval set shows how often; flag uncertain fields |
| Recordings arrive late | No audio eval | Text eval first; the team records its own sample orders |
| ffmpeg or Docker problems on the judges' machine | Disqualified | CI starts the image with no keys on every push; fresh-clone test |
| Sarvam credit runs out | Live link stops | Budget alerts; rate limit; the sample mode still works |
| Scope creep | Nothing finished | The slice order and cut line above |
