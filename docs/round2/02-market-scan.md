# 02 · Market scan: who else solves this (2026-11-27)

**What a market scan is for:** to learn who already serves this user, what they do well, and where the gap is. It
tells us what to build, what *not* to build, and gives the deck an honest "why us" answer.

**How sure we are:** one round of web searches. Vendor pages are marketing, so their claims are marked as such.
Nothing here was tested hands-on.

## 1. The players

| Player | What it does | Voice? | Who speaks to it | Gap for our user |
|---|---|---|---|---|
| **Khatabook, OkCredit, Vyapar, myBillBook** | Digital khata (credit book), GST billing, payment reminders. Very widely used by small shops | A comparison blog says some allow voice entry "in regional languages"; **not confirmed** on their official pages ([thekedarai](https://thekedarai.pages.dev/articles/digital-billing-for-kirana-khatabook-vyapar-okcredit/)). OkCredit lists Tamil as an app language ([okcredit.in](https://okcredit.in/llms.txt)) | The shop owner, **by typing and tapping** | Typing a 13-line order with a size split is slower than the notebook. They start *after* the order is known; they don't capture the spoken order |
| **Flipkart Wholesale WhatsApp bot (built on Sarvam AI)** | Small retailers place wholesale orders **by voice in regional languages** on WhatsApp, with stock checks and payment ([MIT SMR Middle East](https://www.mitsloanme.com/article/flipkart-brings-voice-led-wholesale-ordering-to-whatsapp-with-sarvam-ai/)) | **Yes** | The **retailer (buyer)**, ordering from **Flipkart's** catalogue | Serves Flipkart's own wholesale business. An independent Khaderpet wholesaler can't use it for *his* buyers |
| **Unico Connect (custom build)** | Turns WhatsApp voice notes into purchase orders for a logistics firm; pulls out line items and flags unclear parts; the buyer confirms. Reports 60% faster processing (vendor's own claim) ([Speech Technology](https://www.speechtechmag.com/Articles/Editorial/Case-Studies/Unico-Connect-Builds-AI-Voice-to-Order-System-for-Ashokraj-Transport--Logistics-174957.aspx)) | Yes | Staff of one large firm | A one-off custom project for a big company, not a product a small shop can switch on |
| **WhatsApp order bots** (Zoko, DoubleTick, local agencies) | Catalogues, menus and order forms inside WhatsApp; some add AI ([Zoko case study](https://www.zoko.io/case-studies/farmorg-foods-ai-order-taking), [Innovative AIs](https://innovativeais.com/blog/whatsapp-order-automation-delhi-wholesale)) | Mostly text and buttons; voice in some agency builds | The buyer | Built for brands with a catalogue flow, not for a wholesaler who takes free-form spoken orders in four languages |
| **AI calling agents for distributors** (Edesy, Yellow.ai with Bizom) | An AI **calls** retailers to collect repeat orders ([Edesy](https://edesy.in/blog/distributor-retailer-order-taking-ai-calls-2026)) | Yes, outbound calls | The AI calls the buyer | For big FMCG distributors with thousands of retailers; outbound, not the owner's own inbound orders |
| **Choco AI** (Europe, food wholesale) | Turns orders from voicemail, email and messages into structured orders for food wholesalers ([choco.com](https://choco.com/us/choco-ai)) | Yes | The wholesaler's staff | **The closest match to our idea, abroad.** It shows the model works and has paying customers. Not in India, no Indian languages |

## 2. What this tells us

1. **The idea is validated, not crowded.** Choco (abroad) and Flipkart + Sarvam (in India, for its own catalogue) show
   that "spoken order → structured order" is real and valued. Nobody serves the **independent Indian wholesaler** who
   takes free-form orders from his own buyers in Tamil, Malayalam, Hindi and Kannada.
2. **Don't rebuild Khatabook.** Billing and khata are already solved, cheaply or for free. Our value is the **step
   before them:** capturing the spoken order completely. Bill and khata are outputs of the order, not the product.
   Later, export to Vyapar or Khatabook instead of competing.
3. **Read-back and confirmation are standard.** Unico flags unclear parts and has the buyer confirm. Our read-back
   step is the right design, and the deck can say so.
4. **Big risk to name in the deck:** a large player (Flipkart, Khatabook, Sarvam) could add "voice order capture".
   Our answer: a narrow focus on one trade (garment lots, size splits, minimum quantities, transport) and one
   cluster (Khaderpet), where a general tool gets the details wrong.

## 3. Market size (rough, for the deck; label it as an estimate)

- **Textile MSMEs registered on Udyam:** about 36 lakh (36,00,012) as of 31 Mar 2026 (manufacturing and trade
  together) ([Statista summary of Udyam data](https://statista.com/statistics/721043/india-number-of-msmes-manufacturing-apparel-by-type)).
  This is the outer boundary, not our market.
- **Khaderpet alone:** over 1,200 units (Business Standard, 2017; see the Activity 3 sources).
- **Honest sizing for the deck:** start with one cluster (Khaderpet, ~1,000+ shops), then other garment wholesale
  clusters (examples to check: Surat, Ludhiana, Kolkata's Burrabazar, Chennai's Sowcarpet), then any wholesaler who
  takes spoken orders. We do not have a verified count of garment wholesalers in India.

## 4. Gaps still open

- Does Khatabook or Vyapar really have voice entry in Tamil? Check the apps' Play Store pages (5 min, the friend).
- Choco AI's pricing: a useful anchor for "what a wholesaler pays for this".
