# 00 · The story: Order Kural (draft v1, 2026-11-27)

**Why this document comes first:** the product, the demo and the deck must all tell one story. Like the Dropbox seed
deck: the pain in a few words, how people cope today, the better future, the product, why now, why it wins, and how it
grows. Everything we build must prove a line in this story; anything that proves nothing gets cut.

Evidence labels: **[F]** from the brother-in-law, **[W]** web source, **[H]** our hypothesis (to test).

---

## 1. The pain (four words)

### **"The order lives everywhere."**

A Khaderpet wholesaler posts new stock on his WhatsApp status. Then the orders come, **in pieces** [F]:

- a call: "Two dozen print palazzo, crop tops S M L…"
- a voice note an hour later: "Add the kids' palazzo sets too."
- another call the next day: "Make the crop tops twelve. Send by KPN. Credit."
- sometimes the buyer walks in and changes it again.

The truth of one ₹25,000 order is spread across **calls, voice notes, two notebooks** (a register of customers and a
book of order details) **and his memory** [F]. Then he writes it **again** as a bill and **again** in the khata [F].

## 2. How people cope today

1. **Two notebooks + memory.** Register for who and where; details book for what, sizes, shipped or not [F].
2. **Scroll back through WhatsApp** and replay voice notes to rebuild the order [H].
3. **Khatabook / Vyapar / myBillBook:** fine for bills and khata, but everything must be **typed**, after the order is
   already known [W].
4. **ChatGPT:** can turn *one* voice note into a bill, **once**. It forgets everything after [F: his own challenge].

## 3. The better future

**He keeps working exactly as he does today:** buyers call, he talks, voice notes arrive. **Every piece lands in the
right customer's order on its own.** He hears it read back in Tamil and says "sari". When the order is done, he says
"bill it", and the bill, the khata and the dispatch list all update together. **Nothing to type. Nothing
lost. Nothing written twice.**

## 4. The product

### **Order Kural: the shop's ledger that listens.**

- **Speak or forward any piece** of an order: a new order, "add 2 dozen", "remove crop tops", "KPN transport,
  credit".
- **AI puts each piece in the right customer's order**, as item codes from his own catalogue, and reads the change back
  in his language.
- **Our code does the maths:** his prices, minimum quantities, GST, exact totals.
- **One confirmed order drives everything:** GST bill, khata up if on credit, dispatch list.
- **The same records accountants know** (customer, item, sales order, dispatch, invoice, khata, as in Tally), so it
  can export to Tally or Vyapar later. See `00b-lifecycle.md`.
- **Every line keeps the voice it came from.** Tap a line to hear the original. Settles "but you said two dozen!".

## 5. Why voice and AI are essential here (not decoration)

| Without… | What happens |
|---|---|
| **Voice** | He must type 15-line orders with sizes. He won't: the notebook is faster [F, Round 1]. Buyers already order by voice, so voice is the input whether we like it or not |
| **AI that understands language** | Four languages mixed with English trade words; "rendu dozen", "ovvonnum six", "same as last time". Rules or forms can't parse this |
| **AI that understands *intent* against memory** | "Add the kids' sets too" only makes sense against the open order from yesterday. This is the step ChatGPT can't do, because it has no memory of his shop |
| **Plain code (not AI) for money** | Totals, GST and stock must be exact every time, so the AI only reads, never calculates |

## 6. Why now

1. **Indian-language speech AI got good enough for code-mixed speech.** Sarvam's Saaras v4 has a `codemix` mode for
   exactly "Tamil + English trade words" speech [W]. Flipkart launched voice wholesale ordering on WhatsApp built on
   Sarvam [W].
2. **It got cheap.** About ₹1.5 per order: speech ₹0.49 a minute, AI and voice read-back a rupee more [W, estimate].
3. **Voice notes are already the habit.** 7 billion WhatsApp voice notes a day worldwide [W]; his buyers already order
   this way [F].
4. **AI can now return reliable structured data** (strict JSON schemas), so speech can safely become records.

## 7. Why it wins

- **It doesn't change how he works.** He talks; it listens. (Dropbox's key point: changing behaviour is the hardest
  thing.)
- **It remembers.** Open orders, catalogue, khata, shipping: one place, not two notebooks and a phone.
- **It is exact where it matters.** AI reads; code calculates; nothing is saved without his "sari".
- **It is built for one trade:** garment lots, size splits, minimum quantities, transport names. A general tool gets
  these wrong.

## 8. Competition

| | Speaks his languages | Takes orders by voice | Assembles orders from many pieces | Remembers orders, khata, shipping | For an independent wholesaler |
|---|---|---|---|---|---|
| TallyPrime / Busy / Marg (desktop) | No (typing) | No | No (typed sales orders) | Yes (typed) | Yes |
| Khatabook / Vyapar | Partly (typing) | Unconfirmed | No | Yes (typed) | Yes |
| ChatGPT / Claude | Yes | One note at a time | No | No | Yes, but forgets |
| Flipkart Wholesale bot (Sarvam) | Yes | Yes | No | Flipkart's own | **No:** only Flipkart's catalogue |
| Choco AI (Europe) | No | Yes | Partly | Orders only | Not in India |
| **Order Kural** | **Yes** | **Yes** | **Yes** | **Yes** | **Yes** |

## 9. Business model [H: to test with the brother-in-law]

- **₹299 a month per shop** (hypothesis). Cost to serve ≈ ₹90 a month at 60 orders. Free for the first 50 orders.
- Why he would pay: one wrong ₹25,000 order or one forgotten credit costs more than a year of the app.
- **Ask him:** "Would you pay ₹299 a month for this? What would make it worth it?"

## 10. Launch plan (how we reach the first users and grow)

1. **Design partner:** the brother-in-law's shop uses it for a month; we measure (PRD §7).
2. **The street:** Khaderpet shops sit side by side; his neighbours see it working. Target 10 shops in month 2.
   Over 1,200 units in Khaderpet [W, 2017].
3. **Built-in spread (like Dropbox's shared folders):** every bill and payment reminder reaches a **buyer, who is
   herself a retailer** with her own suppliers and customers. Each bill carries "Made with Order Kural".
4. **Trade bodies:** the Khaderpet traders' association; then other garment clusters (Surat, Ludhiana, Chennai's
   Sowcarpet: to check).
5. **Later:** a real WhatsApp number so voice notes are forwarded straight in; export to Vyapar or Tally.

## 11. The demo (one buyer, three pieces, one bill): what the video shows

1. **Piece 1, a call (he speaks after it):** "Kerala Fancy, Palakkad. Print palazzo rendu dozen. Crop top S M L
   ovvonnum six." → a new order appears for Kerala Fancy with item codes and exact totals; read back in Tamil; "sari".
2. **Piece 2, a forwarded voice note, later:** "Kids palazzo set 24 add pannunga; crop top twelve aakkunga." → the app
   finds Kerala Fancy's open order, shows **what changed**, reads back the change; "sari".
3. **Piece 3:** "KPN transport, credit." → fills transport and payment.
4. **"Bill it"** → GST bill; khata shows Kerala Fancy owes the amount; dispatch list shows the order as "to ship".
5. **Tap a line → hear the original voice.**
6. 10 seconds: built with Wispr Flow by voice. Close on "The shop's ledger that listens."

## 12. What this means for the build (every feature must prove a line above)

| Story line | Must build |
|---|---|
| "The order lives everywhere" → "every piece lands in the right order" | Open orders per customer; AI outputs **changes** (add / change / remove / set field) against the open order |
| "Nothing lost" | Each line linked to its source voice note; missing transport or payment asked by voice |
| "Our code does the maths" | Catalogue with item codes, prices, minimums; GST; totals in paise |
| "One confirmed order drives everything" | Confirm → bill + khata + dispatch list |
| "Doesn't change how he works" | Speak or upload any piece; read-back in his language; "sari" to confirm |
| "Remembers" | Orders board (his register), khata page, to-ship list |
| Judges without keys | Sample conversation (3 pieces) runs on saved AI results |

**Cut:** separate "edit by voice" (pieces cover it); PDF share from the phone (print bill stays); settings pages.
**Future (owner's decision, 27 Nov):** stock, receiving stock by voice, low-stock alerts.
