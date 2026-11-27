# 03 · PRD: Order Kural, Round 2 prototype (v2, 2026-11-27)

**What a PRD is for:** *what* we build and *why*, and how we know it works. The *how* is in the RFC.

**Inputs:** `00-story.md` (the story), `00b-lifecycle.md` (full life cycle, approved by the owner), `01-discovery.md`
(including the 27 Nov call), `02-market-scan.md`, `requirements.md` (competition rules).

**v2 changes:** the product is now *order assembly from many voice pieces* (from the 27 Nov call); stock moved to the
future (owner's decision); scope cut to fit the hackathon.

---

## 1. Problem (from the story)

**"The order lives everywhere."** A Khaderpet wholesaler's order arrives in **pieces**: calls, WhatsApp voice notes,
walk-ins, over hours or days, after he posts stock on his WhatsApp status. He keeps an order register and an order
details book, then writes a bill, then a khata entry. Software like TallyPrime or Vyapar holds the same records, but
needs typing, so he doesn't use it. ChatGPT understands voice but remembers nothing.

## 2. Users

| User | In the prototype |
|---|---|
| **Shop owner** (primary; the brother-in-law) | Speaks or uploads each piece, confirms read-backs, bills, marks shipped |
| Retail buyer (secondary) | Receives the bill and a payment reminder (via WhatsApp share) |

**How many** (deck, labelled estimates): Khaderpet had 1,200+ units (Business Standard, 2017); garment wholesale
clusters across India; ~36 lakh textile MSMEs on Udyam is the outer boundary.

## 3. Product principle

**"Listens like ChatGPT, remembers like Tally."** He talks as he does today; each piece lands in the right customer's
order; the confirmed order makes the bill, the khata entry and the to-ship entry.

## 4. Hackathon scope: how the full life cycle is cut

The competition asks for "**one core flow that works end to end. Not a full product.**" Judges penalise mocking the
core feature but accept faking the periphery (hackathon judging advice; see §11). So the life cycle
(`00b-lifecycle.md`) is cut into three layers:

| Layer | Life-cycle steps | How it is built |
|---|---|---|
| **Core (judged; always real, never faked)** | 2-11: each voice piece → transcript → AI works out the customer and the changes → our code checks them → spoken read-back → spoken "sari" → order updated; more pieces merge into the same order; "bill it" | Live Sarvam speech-to-text, AI and read-back voice; our rules engine and state machine |
| **Supporting (real, but simple)** | 12-15: bill, khata entry, to-ship list, mark shipped, record a payment, reminder link, play the source voice of a line | Plain screens and taps; voice for "bill it" |
| **Periphery (seeded, allowed to be fake)** | 1: item list and shop details | Seeded from the real notebook rates; shop name and GSTIN clearly marked as demo values |
| **Out (future)** | Stock and low-stock alerts; a real WhatsApp number; Tally or Vyapar export; login; several shops | Named in the deck's roadmap |

## 5. The core flow (what the demo shows)

1. **Speak a piece:** hold the mic, or upload a forwarded voice note (WhatsApp Ogg/Opus, M4A, MP3, WAV, WebM).
2. **Transcribe:** code-mixed Tamil, Malayalam, Hindi or Kannada; any length (long notes are split).
3. **Understand against memory:** the AI gets the transcript **plus the list of open orders and the item list**, and
   returns **which customer** and **a list of changes**: add line, change line, remove line, set transport, set
   payment, set city; or a command (bill this order). It never calculates money.
4. **Check (our code):** match items to codes, fill rates, check minimum quantities, flag rates more than 10% off the
   list, recompute totals and 5% GST, list what's still missing (transport, payment).
5. **Show and read back the change:** new and changed lines highlighted; the app speaks **only what changed** and the
   new total, in the speaker's language; if something is missing it asks one short question ("Which transport?").
6. **Confirm by voice:** "sari / seri / aamaa / haan / theek hai / ok" applies the change; "vendaam / cancel" drops it.
   Tap buttons do the same.
7. **Repeat** for each new piece; pieces for the same customer merge into one order.
8. **"Bill it":** final read-back → confirm → numbered GST bill + khata entry (if credit) + to-ship entry.

## 6. Requirements

**P0 = needed to submit. P1 = should have. P2 = only if time allows.**

| ID | Requirement | Story line it proves | P |
|---|---|---|---|
| R1 | Record (hold to talk) and upload voice pieces | "He keeps working as he does" | P0 |
| R2 | Speech-to-text, code-mixed, 4 languages; audio over 30 s works | "In his language" | P0 |
| R3 | AI returns customer + change list as strict JSON, given open orders and items; invalid output never reaches the screen | "Every piece lands in the right order" | P0 |
| R4 | Rules engine in code: item codes, rates, minimums, GST, totals in paise; unit-tested | "Our code does the maths" | P0 |
| R5 | Order card showing what changed, and what's missing | "Nothing lost" | P0 |
| R6 | Spoken read-back of the change in the speaker's language; text fallback | "Hears it read back" | P0 |
| R7 | Confirm or cancel by voice and tap; nothing applied without confirmation | Guardrail | P0 |
| R8 | Several pieces merge into one customer's open order | **The differentiator** | P0 |
| R9 | "Bill it" → numbered GST bill (CGST Rule 46 fields), printable | "Written once" | P0 |
| R10 | Credit orders add a khata entry; a khata page with balances | "Remembers like Tally" | P0 |
| R11 | Each order line keeps its source voice piece; tap to play | "Settles disputes" | P0 |
| R12 | **No keys:** main screen opens with a "key not set" banner; **"Try the sample conversation"** plays 3 recorded pieces through the real pipeline using saved AI results, labelled as such | Competition rule | P0 |
| R13 | `docker compose up` starts everything | Competition rule | P0 |
| R14 | Every step traced: time, provider, cost, errors; `/traces` page | Observability | P0 |
| R15 | Ask one spoken question for a missing transport or payment | "Nothing lost" | P1 |
| R16 | To-ship list; mark shipped (tap) | Life cycle 13 | P1 |
| R17 | Record a payment (tap; voice if time); reminder opens WhatsApp with a drafted text in the buyer's language | Life cycle 14 | P1 |
| R18 | Orders board (his order register): open, billed, shipped | "Remembers" | P1 |
| R19 | Public live link | Competition bonus | P2 |
| R20 | Tamil subtitles on labels | Polish | P2 |

## 7. Success metrics

**A. AI quality, on our eval set** (`05-evalset.md`). Cases are **conversations**: 1-4 pieces each, with the correct
final order.

| Metric | Meaning | Target |
|---|---|---|
| Customer routing | Piece attached to the right open order, or correctly starts a new one | ≥ 95% |
| Change accuracy | Changes (add, change, remove, set) exactly right per piece | ≥ 85% |
| Final order accuracy | After all pieces: every line, size and quantity correct | ≥ 80% of conversations |
| **Silent error rate** | A wrong number applied without being highlighted and read back | **0** |
| Latency | End of speech → read-back starts, for a 30 s piece | ≤ 10 s |
| Cost | Per piece (speech + AI + voice) | ≤ ₹2 |

Targets are first guesses; we adjust after the first run and write down why.

**B. Product (after the hackathon, at the shop; for the deck):** share of orders taken through Order Kural by choice
(> 70% after a month); orders with all key fields filled (> 95%); fewer disputes.

**Launch gate for submitting:** all P0 working; eval run done and reported honestly; fresh clone starts on the
friend's laptop with no keys; video ≤ 3 min; deck PDF with the four required topics.

## 8. Guardrails

1. Nothing changes an order, makes a bill or touches the khata **without his confirmation**.
2. The AI only reports what was said; **our code calculates** every rate, total and tax.
3. Numbers are never invented: unclear → highlighted and asked.
4. If the AI isn't sure which customer a piece belongs to, **it asks** ("Kerala Fancy or Kerala Silks?") instead of
   guessing.
5. Missing keys or failed providers are shown plainly; typing is always a fallback.

## 9. Dependencies (for the deck's "What it depends on")

| Dependency | Use | If it gets costly or stops |
|---|---|---|
| Sarvam Saaras v4 (₹0.49/min) | Speech → text | Google or Gemini audio behind the same interface; open-source AI4Bharat IndicConformer self-hosted; typing |
| Sarvam `sarvam-105b` | Transcript → customer + changes | Gemini Flash behind the same interface; the rules engine doesn't change |
| Sarvam Bulbul (₹2-3 per 1,000 chars) | Read-back | Browser's built-in voice; the order card is always on screen |
| WhatsApp (share links) | Bill and reminder delivery | Any app via the share sheet |
| Wispr Flow | How we built it (dictation) | Wispr's API (invite-only) can become the speech engine later |

About ₹1.5 per order, ~₹90 a month per shop at 60 orders (estimate; measured from traces).

## 10. Open questions

| # | Question | Blocks |
|---|---|---|
| Q1 | Recordings: one order as 2-3 separate voice notes (brother-in-law) | Audio eval set; demo realism |
| Q2 | Typical voice-note length | Long-audio design check |
| Q3 | Would he pay ₹299 a month? | Deck: business model |
| Q4 | Bracketed rates; palazzo minimum 24 or 25; missing rates | Item list |
| Q5 | Bill before or after shipping? (assumed: bill, then ship) | Life cycle order |

## 11. Research behind the scope

- **Judges reward one working end-to-end path over many half-built ones;** get one path working by the halfway mark,
  then improve it ([JetBrains, from the judging table](https://blog.jetbrains.com/ai/2026/06/how-to-win-a-hackathon-notes-from-the-judging-table/);
  [DEV: what judges actually score](https://dev.to/kurbaitaev/what-judges-actually-score-notes-from-a-year-of-hackathon-judging-3p4l)).
- **Fake the periphery, never the core** feature judges came to see
  ([AngelHack](https://angelhack.com/blog/hackathon-tips-for-winners/);
  [Builderbase scoping guide](https://intercom.help/builderbase/en/articles/14836119-builder-s-guide-ch-09-scoping-your-project)).
- **3-minute video budget:** ~25 s user and problem, ~90-100 s one end-to-end action, ~30-45 s how it works
  ([itechguides](https://www.itechguides.com/hackathon-demo-essentials-show-the-project-explain-the-choices)); the
  first 30 seconds set the score ([DEV](https://dev.to/kurbaitaev/what-judges-actually-score-notes-from-a-year-of-hackathon-judging-3p4l)).
- Typical criteria elsewhere: innovation, functionality, usability, impact, presentation
  ([Reskilll](https://blogs.reskilll.com/?p=436); [Builderbase rubrics](https://intercom.help/builderbase/en/articles/14831464-hackathon-playbook-ch-15-judging-rubrics)).
  No Scaler-specific rubric exists publicly.
- Conventional software (Tally, Busy, Marg, Vyapar) and its record chain: `00b-lifecycle.md`.
- GST 5% for garments up to ₹2,500 per piece; WhatsApp links can't attach files; Sarvam's 30 s limit: see the RFC.
