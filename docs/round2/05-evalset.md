# 05 · Eval set v1: how well does the agent understand an order?

**Why an eval:** we measure accuracy instead of claiming it. Every change to the prompt or the guards is re-run
against the same conversations, and the reports are committed as they came out, good or bad.

## The set (`eval/cases.json`)

13 short conversations, each run on a fresh, empty shop through the **text brain**: Sarvam `sarvam-105b` calling our
tools, exactly the path typed messages and uploaded voice notes take.

| Kind | Cases |
|---|---|
| **Real** | The shop's real Hindi customer voice note (Sarvam STT transcript, 35.8 s, 6 items, transport, bank payment, no shop name) |
| Synthetic, labelled | Tamil order in two pieces; change and remove; near-miss customer ("Kerala Fancies"); forwarded note with no shop name; unknown item; rate spoken off-list; transport and payment said later; GST invoice then payment (checks the khata balance); "sari" with nothing waiting; "sari also add ten shorts" (must not confirm); Malayalam-mixed; Kannada-mixed |

## What is scored (`eval/score.py`, unit-tested)

- **Orders fully correct:** customer, every line, transport, payment, invoice count and khata balance all match the
  correct answer. Where the agent should ask (no shop name, near-miss), it must ask and must not save an invented
  order.
- **Line accuracy:** correct lines out of all expected lines.
- **Wrong lines saved ("silent errors"):** saved lines that match no correct line. In a real shop these are the
  costly mistakes, so this number matters most.
- **Claims caught:** turns where the code had to say "that was not added", because the AI claimed an action no tool
  performed.
- **Speed and cost:** turn time p50/p90 and the estimated Sarvam cost.

## Results, in the order they were run (27 Nov)

| Run | What changed before it | Fully correct | Line accuracy | Wrong saved | p50 turn | Cost |
|---|---|---|---|---|---|---|
| baseline | (first run) | 8/13 | 0.50 | 2 | 381 ms | ₹1.42 |
| run 2 | plain-quantity example, "never invent sizes" rule, no empty new orders | 11/13 | 1.00 | 0 | 443 ms | ₹1.46 |
| run 3 | town passed for the invoice; "advance" wording | 12/13 | 1.00 | 0 | 358 ms | ₹1.47 |
| run 4 | **prompt examples rewritten so they no longer copy eval wording (run 3 was inflated by this leak)** | 11/13 | 0.92 | 1 | 378 ms | ₹1.47 |
| run 5 | code check: sizes with numbers must have been said | 10/13 | 0.75 | 0 | 395 ms | ₹1.46 |
| run 6 | keep good lines when one has an invented size; echoes of items without a tool count as unbacked claims | 11/13 | 0.83 | 0 | 402 ms | ₹1.47 |
| **final 1** | Tamil number words turned into digits in code before the AI | **12/13** | **1.00** | **0** | 420 ms | ₹1.47 |
| **final 2** | same code, run again (the AI is not deterministic) | **11/13** | **0.92** | **0** | 390 ms | ₹1.47 |

Reports: `eval/reports/2026-11-27-*.md` and `.json`. Each JSON has every turn: what was said, the tools called and
what was spoken back.

## What the numbers say

- **No wrong line was saved in the last four runs.** When the AI is unsure or wrong, the code turns it into a spoken
  problem or a question; it does not reach the order. This is the property a shop owner needs most.
- **The real Hindi note passed every run after the baseline.** The agent asks which customer, because the note never
  names the shop (no invented "Sir"). After that, one tool call captures the age-band sizes, Girnar Transport and the
  bank payment. "Women's pant" and "teenager girls pant" are refused instead of being saved as girls pant.
- **The remaining misses are safe misses:**
  - **near-miss customer:** the AI decides by itself that "Kerala Fancies" means the open "Kerala Fancy" order and
    reads that name back, instead of asking first. We kept the expected answer strict.
  - **change and remove:** the AI sometimes asks before changing, so the change is still waiting when the
    conversation ends.
- **Run-to-run variation is real:** the same code scored 12/13 and then 11/13. One run of 13 cases is a smoke test,
  not a benchmark.

## Limits (be honest in the deck)

- **12 of the 13 cases are synthetic, and written by us.** We also tuned the prompt after seeing failures. We removed
  the examples that copied eval wording (run 4), but the risk of fitting to this set remains.
- **The text brain skips speech-to-text.** Live voice adds STT errors. Those are checked separately: the four-turn
  live-voice check on 27 Nov was 4/4 correct (see the ledger). Sizes like "S aaru" arriving as "SR" are handled by
  the prompt and the size check.
- **Next:** 20-30 of the owner's own recorded notes (in his voice, reading past orders), run through the live voice
  path, scored the same way.

Run it yourself: `python -m eval.run` (needs `SARVAM_API_KEY`, about ₹1.50 per run).
