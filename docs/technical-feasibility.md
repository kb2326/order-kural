# Technical feasibility of Order Kural, and the Round 2 toolkit (checked 2026-11-17)

## Each step, and whether it is possible today

| Step | How | Status |
|---|---|---|
| Receive WhatsApp voice notes | WhatsApp Business Platform (Cloud API) webhooks deliver incoming audio. "Coexistence" (2025) lets the same number run in the WhatsApp Business app and the API | available ([360dialog](https://docs.360dialog.com/docs/resources/phone-numbers/coexistence), [Telnyx](https://developers.telnyx.com/docs/messaging/whatsapp/coexistence)) |
| Speech to text in Tamil, Malayalam, Hindi and Kannada, with code-mixing | Sarvam AI Saaras (22+ Indian languages, codemix output mode); Google Speech-to-Text as an alternative | available ([Sarvam models](https://docs.sarvam.ai/api/getting-started/models)) |
| Turn the transcript into a structured order | an LLM with a strict JSON schema, then price-list matching and minimum-quantity rules in plain code | standard |
| Read back aloud | Sarvam Bulbul or Google text-to-speech. Tamil is confirmed; check Malayalam per voice model | mostly; text read-back as a fallback |
| GST bill as a PDF on WhatsApp | generate the PDF, send it as a document. Small shops are below the e-invoice (IRN) threshold | standard |
| Khata and reminders | a small database. Business-initiated WhatsApp messages need approved templates and are paid per message | with setup |

## Phone calls (apps cannot record normal calls on Android)

1. **Dictate after the call:** a 20-second voice summary. Simplest and free.
2. **The phone's built-in call recorder:** some Android dialers have one. Share the file to the bot.
3. **A cloud business number** (Exotel, MyOperator, Knowlarity): records every call automatically. Best for a real
   product; costs a monthly fee.
4. **WhatsApp Business calling API:** newer; a later version.

A full recorded call contains bargaining and changes of mind, so the LLM must extract the final agreed order, and
the read-back confirmation is essential.

## Main risks

- **Wrong numbers:** confirm every quantity and rate before saving.
- **Catalogue references** ("the third photo"): version 1 matches item names only.
- **Accents and code-mixing:** test on 20-30 real voice notes from the shop before trusting it.
- **Real launch overheads:** Meta verification and template approvals take days to weeks. A demo can use WhatsApp's
  test number or a web chat UI.

## Wispr Flow's role

Wispr Flow is the builder's dictation tool (writing, prompting the app builder). It is not the product's speech
engine. Whether it has a developer API is unverified; check before planning to use it inside the product.

## Round 2 toolkit to prepare before 27 Nov (see `toolkit/README.md`)

1. Speech to text (Sarvam).
2. LLM extraction to JSON (Gemini or Sarvam).
3. Text to speech (Sarvam Bulbul).
4. A minimal front end: a web page with a mic button, or a Lovable/Bolt app.
5. A WhatsApp test number (optional).

Test each step on real audio in Tamil, Malayalam and Hindi.
