# ADR-006: A no-key sample mode that runs the real pipeline on saved AI results

- **Date:** 2026-11-27 · **Status:** Accepted
- **Context:** the rules say the app "must start and show its main screen without any secret keys… We do not add keys
  for you." A judge without keys would otherwise see only "key not set" messages and never see the product work.
- **Options:** (1) show "key not set" only; (2) a fake demo page; (3) fixture providers that return saved results for
  one recorded sample order, run through the real state machine, rules, bill and khata.
- **Decision:** option 3, labelled clearly on screen as "Sample: saved AI results". With keys set, the same sample
  audio goes to the live providers.
- **Consequences:** judges see the core flow working with zero setup. The fixtures double as test data. We must keep
  the label honest so nobody mistakes saved results for live AI.
