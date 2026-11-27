# ADR-004: Split long voice notes at pauses into pieces under 28 seconds

- **Date:** 2026-11-27 · **Status:** Accepted (revisit after the real voice-note lengths arrive)
- **Context:** Sarvam's quick speech-to-text call rejects audio over 30 s. A 10-15 line order may take a minute or more.
- **Options:** (1) Sarvam batch API (up to 2 hours; asynchronous, needs polling, slower); (2) cut every 28 s
  (fast, but may cut a word in half); (3) cut at the pause nearest each 28 s mark, using ffmpeg's silence detection.
- **Decision:** option 3, with a hard cut at 28 s when there is no pause; pieces are transcribed in parallel and
  joined. Batch API kept as a fallback.
- **Consequences:** needs ffmpeg in the Docker image. Unit tests cover the cut-point logic. If the eval shows errors at
  the joins, we switch to the batch API.
