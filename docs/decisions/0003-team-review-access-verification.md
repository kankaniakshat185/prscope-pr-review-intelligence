# 0003 — Team-shared review visibility: a live permission check, not review history

## Problem
The original gate for viewing a teammate's saved review of a repository was
"have you personally analyzed this repo with PRScope before." That's
trivially bypassable: it proves nothing about the *viewer's* real access to
the repo, only that the shared backend's own GitHub token could once see it.

## Approach
Replaced it with `verify_repo_access(owner, repo, github_token)`: a live
GitHub API check against the viewer's own personal access token.
- Private repo → any non-404 response grants access (you can see it, you
  have access).
- Public repo → requires `permissions.push` or `permissions.admin`
  specifically — read access is universal for public repos and proves
  nothing about real team membership.

## Result
Real, access-controlled team visibility instead of a bypassable heuristic.
Wiring this in required adding `X-Github-Token` to the backend's CORS
`allow_headers` list — a gap caught by hand-running a real browser `OPTIONS`
preflight request locally, since a Python `TestClient` hitting routes
directly never exercises browser CORS behavior and would have shipped a
silently-broken feature.

## Tradeoff
Every team-view request now costs a live GitHub API call instead of a local
DB lookup.

**Code:** `backend/app/services/github.py` (`verify_repo_access`),
`backend/app/api/endpoints.py` (`_has_team_access`), `backend/app/main.py`
(CORS)
