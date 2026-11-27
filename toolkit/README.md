# Round 2 toolkit (to build before 27 Nov)

A reusable voice pipeline, so the 3-day build on the organisers' problem starts from working parts:

audio → speech-to-text (Indian languages, code-mixed) → LLM extraction to JSON → rules and checks → spoken and
written read-back → output (PDF, WhatsApp link, simple database)

## Planned pieces

1. **`stt`:** Sarvam Saaras (codemix), returning text and word confidences.
2. **`extract`:** an LLM call with a JSON schema, plus a fuzzy match against a list.
3. **`tts`:** Sarvam Bulbul, speaking in the user's language.
4. **`ui`:** a mobile web page with a hold-to-talk mic and a chat view.
5. **`tests`:** real voice clips in Tamil, Malayalam and Hindi (with consent), checking the extracted numbers.

## Keys

Keys go in `.env` (git-ignored): `SARVAM_API_KEY`, `GEMINI_API_KEY`, and later `DISCORD_BOT_TOKEN`.
