# Eval

See `docs/round2/05-evalset.md` for what is measured and the results.

- `cases.json`: the conversations and their correct answers (1 real, 12 synthetic, labelled).
- `score.py`: the scorer (unit tests in `tests/test_eval_score.py`).
- `run.py`: runs every case on a fresh shop through the text brain; `python -m eval.run` (needs `SARVAM_API_KEY`).
- `reports/`: every run, committed as it came out.
