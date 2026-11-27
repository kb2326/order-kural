# ADR-005: Prices, rules and totals are computed by our code, never by the AI

- **Date:** 2026-11-27 · **Status:** Accepted
- **Context:** a wrong total on a ₹25,000 order costs money and trust. AI models can make arithmetic slips and can
  invent plausible numbers.
- **Decision:** the AI only *reads* the transcript into fields (what was said). Our tested Python code matches items,
  fills rates, applies minimum quantities, computes totals and GST in integer paise, and writes the read-back text.
- **Consequences:** totals are exact and testable; the AI's job is small, so it is easier to evaluate. The rules must
  be kept up to date by hand (a price-list settings page later).
