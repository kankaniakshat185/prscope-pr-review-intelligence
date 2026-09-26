# 0001 — Empirically calibrated incident-retrieval threshold

## Problem
`find_similar_incidents` converts a ChromaDB distance into a 0–100 similarity
score, then needs a cutoff to decide whether a past incident is genuinely
*related* to a PR — not just superficially similar. Picking that cutoff by
guessing a round number risks either hiding real matches or surfacing noise.

## Approach
`retrieval_eval.py` measures real score distributions against a hand-labeled
15-query evaluation set (`app/data/incident_eval_queries.py`) instead of
trusting an assumed number: genuinely unrelated queries ("fix typo in
changelog", "bump lodash version") scored 6–32; genuine top-1 matches on
realistic PR-length text scored 41–80.

## Result
The original `MIN_DISPLAY_SCORE = 60` — set in the project's early
3-stub-incident era and never revisited — sat inside the range where real,
correct matches actually land, silently hiding 12 of the 15 genuine matches
in the eval set. Recalibrated to `35`, the empirical gap between the two
distributions. Measured retrieval quality after the fix: **93% precision@1**,
**100% hit-rate@3**.

## Tradeoff
Calibrated against one 15-query set, not a statistically large sample — a
reasoned calibration based on real measurement, not a guarantee that holds
at every scale or against every incident corpus.

**Code:** `backend/app/services/incident_similarity.py`,
`backend/app/services/retrieval_eval.py`
