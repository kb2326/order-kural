# Activity 2: Prompt (SUBMITTED; quality check passed, evaluation pending; 789 words; up to 50 points)

The text below is exactly as submitted. Known small slips:
- "Kanada" should be "Kannada".
- Step 3 still says "all three languages" though four are listed.
- The crop-top rate (75) is an estimate.
- The palazzo minimum is 24 here; the owner first said 25.

Your users and their languages:
Build a mobile-first web app called "Order Kural", a voice ordering assistant for small garment wholesalers in Khaderpet, Tirupur, Tamil Nadu. The final product runs inside WhatsApp; for this prototype, build a WhatsApp-style chat screen (green header, chat bubbles, a large hold-to-talk microphone button, and an "Upload voice note" button for WhatsApp audio files). Primary user: the shop owner, who takes 25 to 30 orders every two weeks by phone and voice note, working one-handed. Secondary users: staff, who view confirmed orders, and retail buyers, who receive bills. Languages: Tamil (Kongu accent), Malayalam (buyers from Kerala), Kanada and Hindi, often mixed with English garment words such as "palazzo", "crop top", "co-ord set", "XL" and "dozen". Interface labels are in English with Tamil subtitles; replies use the language the owner speaks.

The voice flow, step by step:
1. The owner holds the mic and speaks, or uploads a forwarded buyer voice note. Example: "Kerala Fancy, Palakkad. Print palazzo rendu dozen, 68 rate. Crop top S M L ovvonnum six. Kids palazzo set 24. KPN transport. Credit."
2. Send the audio to a speech-to-text API that supports Indian languages and code-mixing (Sarvam AI Saaras in codemix mode; API key in Settings). Show the transcript under the voice bubble.
3. Send the transcript to an LLM with a strict JSON schema: buyer_name, buyer_city, items [name, quantity, sizes {S, M, L, XL}, rate], transport, payment ("cash", "UPI" or "credit"). Convert number words in all three languages ("rendu", "randu", "do" = 2; "dozen" or "darjan" = 12; "ovvonnum" or "each" = per size).
4. Match each item to the price list  and fill missing rates. Price list in rupees per piece, editable in Settings: Boys T-shirt 55, Girls T-shirt 55, T-shirt S-M-L 60, Shorts set 85, Pant set 95, Stone pant 45, Plain palazzo 65, Print palazzo 68, Kids pant 28, Popcorn pant set 95, Girls pant 55, Kids palazzo set 120, Crop top 75; the owner adds other items in Settings.
5. Apply the shop's minimum-quantity rules: kids' items 10 per size, crop tops 6 per size, pants and palazzos 24 pieces (2 dozen), shorts 10 pieces.
6. Show the order card, then read it back aloud with text-to-speech in the owner's language.
7. The owner replies by voice: "sari", "seri" or "theek hai" confirms; "change print palazzo to 30" edits one line; "cancel" discards.
8. After confirmation, the owner says "GST bill". Generate a PDF tax invoice: shop name, GSTIN, buyer, date, S.No, item, HSN code (6104 or 6111), quantity, rate, amount, 5% GST and grand total. Show a "Send to buyer on WhatsApp" button (wa.me link with the PDF).
9. If payment is credit, add the total to the buyer's khata. The Khata tab lists buyers with balances and a "Send reminder" button that drafts a polite reminder in the buyer's language.

What the product says or shows back:
After step 2: "Got the order from Kerala Fancy, Palakkad. Checking items."
Order card: a table with S.No, Item, Qty, Sizes, Rate and Total, a grand total, and transport and payment chips; unclear fields are highlighted yellow.
Spoken read-back (Tamil example, mirrored in Malayalam or Hindi): "Kerala Fancy. Print palazzo 24, rate 68. Crop top S, M, L, six each. Kids palazzo set 24. Total 5,862 rupees. KPN transport, credit. Sari-ya?"
After confirming: "Order saved. Say 'GST bill' to make the bill."
After billing: "GST bill ready, 6,155 rupees with GST. Sending to Kerala Fancy."
Rule warning: "Crop top minimum is 6 per size. You said 4 for M. Make it 6?"

Noise, accents, mixed languages and misheard input:
- Background noise or a clip shorter than 2 seconds: "I couldn't hear clearly. Please say it again closer to the phone." Keep any partial transcript.
- Words with confidence below 0.7: highlight them yellow and ask only about that part: "Was it 24 or 34 print palazzo?"
- Quantities and rates are always read back before saving. Never save an order without a voice or tap confirmation.
- Unknown item name: show the 3 closest price-list matches as buttons and ask "Did you mean print palazzo?"
- Missing buyer name or payment type: ask one short question at a time, then continue.
- Language switches mid-sentence are normal: transcribe in codemix mode and never ask the user to pick a language.
- A rate more than 10% away from the price list: confirm it ("Rate 58 is lower than 68. Keep 58?"), because it may be a negotiated price.
- If speech-to-text fails, show a text box so the owner can type, and keep the audio for retry.

Seed one demo order (13 lines, 26,552 rupees, credit) and three buyers with khata balances, so it works without login.
