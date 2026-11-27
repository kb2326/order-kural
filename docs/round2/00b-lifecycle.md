# 00b · The full life cycle of one order in Order Kural (2026-11-27)

Scope decision (owner, 27 Nov): **stock is a future feature** (a different use case). This round covers the order,
from the first piece to bill, khata and dispatch.

## How businesses do this today with software (instead of notebooks)

Indian traders who move off notebooks mostly use **TallyPrime** (self-reported 2.7M+ businesses), **Busy**
(4 lakh+), **Marg**, or mobile apps **Vyapar** (claims 1.5 crore+) and **myBillBook**. Garment editions exist for
Tally, Busy (≈₹15,000 a year) and Marg (≈₹13,900). All vendor figures, not independent.

They all use the same chain of records (Tally's names):

| Record | What it is | The brother-in-law's equivalent today |
|---|---|---|
| **Customer (ledger) master** | Name, place, phone, GSTIN | Notebook 1 (order register) |
| **Item (stock item) master** | Item code, name, sizes, rate, HSN | His memory and the rate list |
| **Sales order** | What the customer ordered; stays "pending" until delivered | Notebook 2 (order details) |
| **Delivery note** | What was dispatched, when, by which transport | "Shipped or not" mark in notebook 2 |
| **Sales invoice** | The GST bill | Handwritten bill |
| **Receipt + outstanding report** | Payments received; who owes what | Khata book |

**Why he doesn't use them:** every record must be **typed** into a desktop or app, with item masters set up first.
Tally even publishes a guide on replacing "separate order sheets" with its order management, but all of it is typing,
after the order is already clear in his head.

**What Order Kural changes:** the **same records** (customer, item, sales order, dispatch, invoice, khata), so an
accountant understands them and they can be exported to Tally or Vyapar later, but **created and updated by voice,
from the pieces as they arrive**.

## The life cycle, step by step (example: Kerala Fancy, Palakkad)

### Once, at setup (10 minutes)
- His **item list** is loaded: item code, name, sizes, rate, minimum quantity, HSN (e.g. `PP-68` Print palazzo ₹68,
  min 24). For the prototype we seed it from his real notebook rates.
- His **shop details** for the bill: name, address, GSTIN.

### Day 1, 11:00: a buyer calls after seeing his WhatsApp status
1. After the call, he holds the mic and says (in Tamil + English): *"Kerala Fancy, Palakkad. Print palazzo rendu
   dozen. Crop top S M L ovvonnum six."*
2. **Speech to text** turns it into text (Sarvam). The **audio file is kept**, linked to this order.
3. **AI reads the text against what the app already knows:** is there an open order for "Kerala Fancy"? No, so this
   is a **new order**. It returns a list of changes: *add PP-68 × 24; add CT-75 S6 M6 L6*. It does **not** calculate
   money.
4. **Our code checks the changes:** item codes found, rates from his list, minimums met (24 palazzo ✔, 6 per size ✔),
   line totals, GST 5%, grand total. Transport and payment are missing, so they are marked "to ask".
5. **The screen** shows Kerala Fancy's order card; the app **reads it back in Tamil**: "Kerala Fancy, Palakkad. Print
   palazzo 24 at 68. Crop top S, M, L, six each. Total ₹3,000 plus GST. Sari-ya?"
6. He says **"sari"**. Saved as a **pending order** (Tally's "sales order"). Nothing is billed yet.

### Day 1, 16:30: the same buyer sends a WhatsApp voice note
7. He forwards it (uploads the audio file) to Order Kural: *"Kids palazzo set 24 add pannunga, crop top twelve
   aakkunga."*
8. The AI sees Kerala Fancy's **open order** and returns changes: *add KPS-120 × 24; change CT-75 to 12 per size*.
9. The screen shows **what changed** (new line in green, changed quantities highlighted) and reads back **only the
   change** and the new total. He says "sari". The order now has **two voice sources**; each line remembers which.

### Day 2, 10:00: a call to finish it
10. *"Kerala Fancy, KPN transport, credit."* Transport and payment are filled. Nothing is missing now.

### Day 2, 10:05: bill it
11. He says **"bill it"** (or taps). The app reads the final order and total once more; he confirms.
12. **One confirmed order updates everything at once:**
    - a **GST bill** with an invoice number (print, or save as PDF and send on WhatsApp);
    - the **khata**: Kerala Fancy owes ₹X (credit);
    - the **dispatch list**: "to ship by KPN".

### Day 2, evening: dispatch
13. He marks it **shipped** (tap, or says "Kerala Fancy shipped"). It leaves the to-ship list.

### Later: payment
14. When money comes in, he says *"Kerala Fancy paid 10,000"*; the khata balance drops. A **"Remind"** button drafts a
    polite reminder in the buyer's language and opens WhatsApp with the text.

### Any time: a dispute
15. "I said one dozen, not two!" He taps the line and **plays the original voice note** it came from.

## Where is it saved? A database, not a notebook

Everything goes into a **database** (SQLite, a single file on the computer or server). Unlike a notebook it can be
searched, totalled and linked:

| Table | One row per… | Replaces |
|---|---|---|
| `customers` | buyer (name, place, phone) | Notebook 1 |
| `items` | product (code, name, sizes, rate, minimum, HSN) | Memory / rate list |
| `orders` | order (customer, status: pending → billed → shipped, transport, payment) | Notebook 2 header |
| `order_lines` | item in an order (code, sizes, quantity, rate, **source voice note**) | Notebook 2 lines |
| `voice_notes` | piece of audio (file, transcript, time, which order) | WhatsApp scroll-back and memory |
| `invoices` | GST bill (number, date, totals) | Handwritten bill |
| `khata_entries` | credit or payment (customer, amount) | Khata book |
| `traces` | step the AI took (time, cost, errors) | (new: lets us check the AI) |

## What it solves, compared with the notebooks

| Today | With Order Kural |
|---|---|
| One order is spread across calls, voice notes, two notebooks and memory | One order record per customer, built from every piece, with each piece's audio attached |
| Written 3 times (order book, bill, khata) | Spoken once; bill and khata come from the confirmed order |
| "Which orders are still to ship?" means reading the notebook | A to-ship list |
| "Who owes me what?" means adding up the khata by hand | Balances per buyer, and a reminder button |
| Disputes are his word against the buyer's | Play the original voice note |
| Typing into Tally or Vyapar is too slow, so he doesn't | Nothing to type |

## Future (not this round)

- **Stock:** items received by voice ("200 palazzo arrived"), stock reduced on billing, low-stock alerts.
- A real WhatsApp number so buyers' voice notes reach Order Kural directly.
- Export to Tally or Vyapar.
