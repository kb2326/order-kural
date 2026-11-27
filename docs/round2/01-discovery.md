# 01 · Discovery: Order Kural (started 2026-11-27)

**What discovery is for:** before designing anything, be sure we understand the user, their problem and what we
don't yet know. The output is a list of facts (with how sure we are of each) and the riskiest guesses to test first.

**Evidence labels:** **[F]** fact from the shop (the owner's brother-in-law), **[N]** seen in the real notebook page,
**[W]** web source (weaker), **[G]** our guess, not yet checked.

## 1. Who the user is

**Primary user: the wholesale shop owner** (persona based on the brother-in-law, Khaderpet, Tirupur).

- Sells women's and kids' wear in lots: crop tops, co-ord sets, palazzos, leggings, shorts, pant sets. [F]
- Speaks Tamil (Kongu); buyers speak Tamil, Malayalam, some Hindi and Kannada, mixed with English trade words
  ("palazzo", "XL", "dozen"). [F]
- Takes orders while doing other work, often one-handed. [F, Round 1]
- Uses WhatsApp daily; writes orders in a paper notebook. [F]

**Secondary users:**
- **Staff** who pack orders from handwritten notes. [F]
- **Retail buyers** (shops in Tamil Nadu, Kerala, Karnataka) who receive goods, bills and payment reminders. [F]

## 2. How the work is done today

1. A buyer asks for the catalogue (WhatsApp photos). [F]
2. The buyer orders by **phone call or WhatsApp voice note**: items, quantity, sizes, colour, transport. [F]
3. The owner writes the order in a **notebook**: S.No, Item, Quantity, Rate, Total. [N]
4. He converts it into a **normal bill or a GST bill**, by hand. [F]
5. Credit orders go into a **khata book** (money to collect and to pay). [F]
6. Staff pack from the notes; goods go out by a transport service. [F]

**Volume:** 25-30 orders every two weeks, so about 50-60 a month. [F, corrected 20 Nov]
**Order size:** 10-15 lines, ₹20,000-30,000. One real page: 13 lines, ₹26,552, arithmetic correct. [N]

## 3. Pain points, ranked by how sure we are

| # | Pain | Evidence | Sure? |
|---|---|---|---|
| 1 | **Key details are not written down:** buyer name, date, size split, transport and payment status are missing on the real notebook page; they live in the voice note or his memory | [N] the page has these blank | **High** |
| 2 | **The same order is written up to three times** (notebook → bill → khata) | [F] | High |
| 3 | **Credit is hard to follow up:** khata is on paper; reminders depend on memory | [F] khata exists; [G] that money is lost | Medium |
| 4 | **Mistakes:** wrong items, sizes, rates, dispatches | [G] the notebook arithmetic was correct; we have **no count of real mistakes** | **Low: test it** |
| 5 | **Time spent** | [G] at ~2 orders a day, time is a weak argument | Low |

**What this changes (a discovery insight):** with about 2 orders a day, **"saves time" is a weak pitch.** The strong
pitch is **"nothing gets lost":** every detail of a ₹25,000 order is captured once, in one record, confirmed by voice,
and credit is followed up. The demo and deck should lead with completeness and credit, not speed.

## 4. Jobs to be done (what the user is really trying to get done)

1. "When a buyer speaks an order, **capture all of it correctly** without stopping my work."
2. "**Give the buyer a proper bill** quickly, so they trust me and pay."
3. "**Know who owes me what**, and remind them without an awkward call."

## 5. Riskiest assumptions (test these first)

| # | Assumption | Why it could be wrong | How we test it (by when) |
|---|---|---|---|
| A1 | **Speech-to-text gets Tamil code-mixed orders right, especially numbers and sizes** | Accents, trade words, "rendu dozen", shop noise; no published Tamil accuracy | **Eval set** of 10-20 spoken orders with the correct answer (28 Nov) |
| A2 | An LLM can turn the transcript into the **final** order (not the bargaining) | Calls contain changes of mind | Same eval set, with some messy orders |
| A3 | The owner would **speak or forward** the order instead of writing it | Habit; trust | Ask the relative (today); a short trial after the hackathon |
| A4 | Voice notes are **under 30 seconds** (Sarvam's quick API limit) | A 13-line order may take a minute | Ask for real note lengths (today) |
| A5 | Credit follow-up is a real money problem | No data yet | Ask the relative (today) |

## 6. Questions for the relative (phone call today, ~15 min; the friend can do this)

1. In the last two weeks, how many orders went wrong? What went wrong (item, size, rate, transport, payment)?
2. What did one mistake cost you (re-dispatch, discount, an unhappy buyer)?
3. Right now, how much credit is pending, and how much is older than a month? (A rough range is fine.)
4. How do you remind buyers to pay today? How often do they pay late?
5. How long is a typical order voice note? (30 seconds, 1 minute, longer?)
6. Do buyers mostly call or send voice notes? Roughly what share of each?
7. What are the bracketed second rates in the notebook (55 (56), 65 (68))?
8. Palazzo minimum: 24 or 25? Crop-top, co-ord set and leggings rates?
9. Would you speak the order into your phone after a call, if it then made the bill for you? What would stop you?
10. **Could you record 5-10 orders in your own voice** (read from old notebook pages, the way buyers speak them)?

**Privacy note:** use the relative's own voice reading past orders, **not buyers' real voice notes** (the buyers did
not agree to be recorded for this). Real buyer names can be replaced with made-up shop names.

## 6b. What the web says about these questions (general context, not about this shop)

| Question | Web answer | Source quality |
|---|---|---|
| How long do buyers take to pay? (Q3-Q4) | Indian SMEs wait **73 days on average** for invoice payment ([Recordent 2026, via MediaBrief](https://mediabrief.com/recordent-report-highlights-working-capital-stress-for-indian-smes-as-average-overdue-receivables-cross-%E2%82%B93-83-crore/)). In the garment trade, normal credit is **90-120 days, often stretching to 180** ([Indian Textile Journal](https://indiantextilejournal.com/msme-payment-amendment-spurs-garment-sector-concerns/)) | Industry reports; formal invoices, not khata |
| How much money is stuck? (Q3) | About **₹8.1 lakh crore** of MSME payments are delayed (Economic Survey 2025-26, via [KNN](https://knnindia.co.in/news/newsdetails/msme/economic-survey-flags-delayed-payments-lack-of-access-to-formal-credit-as-key-challenges-for-msmes)). For **micro** enterprises, about **66% of sales** are stuck as delayed receivables ([GAME / D&B report](https://www.dnb.co.in/file/reports/Delayed-Payments-Report.pdf)) | Strong (government / D&B); all MSMEs, not garment wholesale |
| How long is an order voice note? (Q5) | **No measured average found.** WhatsApp sees 7 billion voice notes a day worldwide ([TechCrunch](https://techcrunch.com/2022/03/30/people-are-sending-7-billion-voice-messages-on-whatsapp-every-day)). Business advice is to keep notes under a minute; one Indian vendor's transcription stops at 1 minute ([Exotel docs](https://docs.exotel.com/intelligent-chat-agent/whatsapp-voice-note-support)) | Weak; **design for 30-90 seconds** until the relative answers |
| How often do orders go wrong? (Q1-Q2) | **No data found** for small wholesalers. A vendor reports 60% faster processing from voice-note-to-order automation ([Speech Technology](https://www.speechtechmag.com/Articles/Editorial/Case-Studies/Unico-Connect-Builds-AI-Voice-to-Order-System-for-Ashokraj-Transport--Logistics-174957.aspx)) | Vendor claim |

**What this changes:** the web makes **credit (pain 3) look stronger than we rated it:** delayed payment is the best
documented problem for micro businesses. Raise it from Medium to **Medium-High**, pending the relative's numbers.
**Voice-note length is a design risk:** the app must handle notes longer than Sarvam's 30-second quick limit.

## 6c. Call with the brother-in-law (2026-11-27): what we learned [F]

1. **Two notebooks, not one.** Book 1 is an **order register**: customer name and place. Book 2 holds **order
   details**: product, size, quantity, and whether **shipping has happened**. (So the notebook page we saw earlier was
   the details book; the buyer name lives in the other book. Pain #1 becomes "one order is split across two books and
   has to be matched by hand", not "details are never written".)
2. **Orders arrive in fragments.** His WhatsApp **status or broadcast message** (catalogue photos) triggers buyers to
   follow up by **several calls and voice notes, stitched together over time**, or they come in person. **An order is
   almost never one clean voice note or call.**
3. **His wish: one place for everything.** Each product saved with an **item code**, quantity, price and details;
   **stock maintained, with a low-stock alert**; the **bill generated**; the **khata maintained**.
4. **His challenge:** "If I just save a voice note in your system and it makes a bill, ChatGPT or Claude could do
   that too. What is the real use?"

**Still unanswered** from the question list: real voice-note lengths, how often orders go wrong, pending credit,
the bracketed rates, the recordings.

### What this changes

- **The real job is assembling an order from many fragments** (several calls and voice notes, over hours or days,
  with additions and changes), keeping it linked to the customer, and carrying it to bill, khata, stock and shipping.
  A one-shot "voice note → bill" is not the product; ChatGPT already does that.
- **Why not ChatGPT (the answer to his challenge):** ChatGPT forgets. It does not keep his price list, item codes,
  stock, open orders per customer, khata balances or shipping status; it does not merge the 4th voice note into the
  order from the 1st; its arithmetic and rates are not guaranteed; and it does not produce numbered GST bills or
  low-stock alerts. **ChatGPT is a calculator; Order Kural is the shop's ledger that listens.**
- **New pain ranking:** (1) assembling fragmented orders; (2) two books plus a bill plus a khata kept in sync by hand;
  (3) credit follow-up; (4) stock not tracked (no low-stock warning); (5) mistakes (still unmeasured).

## 6d. First real customer voice note (2026-11-27) [F]

The brother-in-law forwarded one real customer order (WhatsApp voice note, 35.8 s, **Hindi**). The audio stays
private (`data/private/`, git-ignored). What it says, as the customer also wrote it down:

| # | Item | Size band | Qty |
|---|---|---|---|
| 1 | Girls pant | 1-10 yrs | 50 pcs |
| 2 | Teen girls pant | 11-25 yrs | 50 pcs |
| 3 | Women's pant | 25-30 yrs | 50 pcs |
| 4 | Girls T-shirt | 1-10 yrs | 50 pcs |
| 5 | Girls T-shirt | 10-25 yrs | 50 pcs |
| 6 | Women's T-shirt | 25-30 yrs | 50 pcs |

Plus: "book it today with **Girnar Transport**, send me the company **account number**, I'll pay."

**Sarvam Saaras v4 test** (`mode=codemix`, `language_code=unknown`): detected `hi-IN`; every item, size band,
quantity and the transport name came out right. Codemix output keeps English trade words in Latin script
("girls pant", "50 piece", "Girnar Transport"), which is easier for the AI step than full Devanagari.

**What this changes**

- **Sizes are often age bands**, not S/M/L. The order model already stores sizes as free labels, so "1-10 yrs" fits.
- **Customers forward their own voice notes, in their own language** (here Hindi, not Tamil). So there are two kinds
  of piece: a **customer's forwarded voice note** (the order itself) and the **owner's own voice** (his summary of a
  call, plus commands like "sari", "bill it"). Both go through the same pipeline.
- **Payment can be advance by bank transfer** ("send the account number"), not only cash, UPI or credit.
- **Splitting at a fixed time cut a phrase in half** ("...50." | "50 piece..."), which risks counting a quantity
  twice. This confirms ADR-004: split at pauses, and let the AI see the joined transcript.
- **Rates for women's and teen items are not in our list yet.** Ask the owner; don't guess.
- This note is a good **eval case** (Hindi, 6 lines, transport and payment in one piece).

## 7. What "success" means for this round

- **For the user:** one spoken order becomes a confirmed, complete order record, a bill and (if credit) a khata entry.
- **For the build:** the flow works end to end in Tamil; measured accuracy on our eval set (fields and numbers right).
- **For the judges** (rules, not a published rubric; see `requirements.md`): starts with one command and no keys;
  voice is the main way in; one flow works end to end; a clear deck and a demo video under 3 minutes.

## 8. Status

- [x] Facts from Round 1 research gathered
- [ ] Relative's answers to section 6 (pending; paste them here)
- [ ] 5-10 recorded orders for the eval set
- Next: `02-market-scan.md`
