# ADR-001: Sarvam for speech, extraction and voice, behind swappable interfaces

- **Date:** 2026-11-27 · **Status:** Accepted
- **Context:** we need speech-to-text for code-mixed Tamil, Malayalam, Hindi and Kannada, an AI model that returns
  strict JSON, and text-to-speech in the same languages. We hold a working Sarvam key (₹100 free credit). The Gemini
  key's project may have no prepaid credit. The **Wispr Flow API** is "exclusive access" (organisation approval via
  enterprise@wisprflow.ai), billed per contract, and its docs do not name Tamil, Malayalam or Kannada.
- **Options:**
  1. Sarvam for all three. One key; Indian languages are its focus; STT supports `codemix` and `keyterms`; chat
     supports `json_schema` structured output; TTS lists ta, ml, kn, hi.
  2. Sarvam speech + Gemini extraction. Strong JSON output, but a second key and billing setup.
  3. Wispr API for speech. Best fit for the sponsor, but not available to us and language support unconfirmed.
- **Decision:** option 1. Each job sits behind an interface (`STTProvider`, `Extractor`, `TTSProvider`), so Gemini or
  Wispr can be swapped in without touching the rules engine or flow. We email Wispr today asking for hackathon access
  and language support.
- **Consequences:** one vendor is a single point of failure, so the deck must name fallbacks (RFC §6). Sarvam returns
  no word-level confidence, so "unclear" flags come from extraction and rules.
