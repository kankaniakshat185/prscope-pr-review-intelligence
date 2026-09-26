# 0004 — A non-atomic check-then-insert on first login

## Problem
Users intermittently hit a raw "Internal Server Error" on their very first
GitHub login — working fine on an immediate retry. Invisible in normal
development testing, because it only affects a brand-new identity's
first-ever OAuth callback, once per identity, ever.

## Approach
Root-caused to the callback's check-then-insert pattern against `github_id`
(a `unique=True` column): query for an existing user, and if none exists,
insert one. Two callbacks racing for the same brand-new identity — a
double-click, or a user retrying immediately after a slow first request —
could both see "no existing user" and both attempt an insert; the loser's
`db.commit()` raised an unhandled `sqlalchemy.exc.IntegrityError`. Fixed with
a catch/rollback/re-query recovery path: on `IntegrityError`, roll back and
re-query for the row the winning request just created, instead of crashing.

## Result
`tests/test_login_race_condition.py` reproduces the actual race (a second,
independent DB session inserts the "winning" row at the exact moment the
first session's commit fails) rather than only asserting the recovery code
path exists. The losing request now returns the same successful login
response as the winner. A genuinely-unrecoverable case (the row still
missing after re-query) returns a clean, actionable error instead of a raw
500.

**Code:** `backend/app/api/endpoints.py` (`github_callback`)
