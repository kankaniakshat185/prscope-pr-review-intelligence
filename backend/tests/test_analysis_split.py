import time
from unittest.mock import AsyncMock, patch

FAKE_PR_DATA = {
    "owner": "octocat", "repo": "Hello-World", "number": 1,
    "title": "Test PR", "description": "", "additions": 10, "deletions": 2,
    "changed_files": 1, "files": [{"filename": "x.py", "patch": "+print('hi')"}],
}


def _fake_llm_response(*args, **kwargs):
    class Resp:
        status_code = 200
        def json(self):
            return {"candidates": [{"content": {"parts": [{"text": "[]"}]}}]}
    return Resp()


def test_analyze_returns_deterministic_fields_only(client, mock_token):
    with patch("app.api.endpoints.fetch_pr_data", new=AsyncMock(return_value=FAKE_PR_DATA)), \
         patch("app.api.endpoints.fetch_architecture_rules", new=AsyncMock(return_value=None)):
        r = client.post(
            "/api/analysis/analyze",
            headers={"Authorization": f"Bearer {mock_token}"},
            json={"repo_url": "https://github.com/octocat/Hello-World", "pr_number": 1},
        )

    assert r.status_code == 200
    body = r.json()
    for field in ("risk_score", "impact_analysis", "architecture_violations", "changed_symbols", "reviewability", "pr_title", "has_tests"):
        assert field in body
    for field in ("review_checklist", "suggested_comments", "executive_summary", "jira_context"):
        assert field not in body  # these belong to /analyze/enrich now


def test_enrich_returns_llm_fields_only(client, mock_token):
    with patch("app.api.endpoints.fetch_pr_data", new=AsyncMock(return_value=FAKE_PR_DATA)), \
         patch("app.api.endpoints.fetch_architecture_rules", new=AsyncMock(return_value=None)), \
         patch("app.services.llm.settings.GEMINI_API_KEY", "fake-key"), \
         patch("app.api.endpoints.asyncio.sleep", return_value=None), \
         patch("requests.post", side_effect=_fake_llm_response):
        r = client.post(
            "/api/analysis/analyze/enrich",
            headers={"Authorization": f"Bearer {mock_token}"},
            json={"repo_url": "https://github.com/octocat/Hello-World", "pr_number": 1},
        )

    assert r.status_code == 200
    body = r.json()
    for field in ("review_checklist", "suggested_comments", "executive_summary", "jira_context", "security_findings"):
        assert field in body
    for field in ("risk_score", "impact_analysis", "pr_title"):
        assert field not in body  # already delivered by /analyze


def test_analyze_security_findings_have_no_ai_fields_yet(client, mock_token):
    fake_finding = [{"name": "X", "severity": "High", "file": "x.py", "confidence": 90, "reason": "r", "recommendation": "rec", "snippet": "s"}]
    with patch("app.api.endpoints.fetch_pr_data", new=AsyncMock(return_value=FAKE_PR_DATA)), \
         patch("app.api.endpoints.fetch_architecture_rules", new=AsyncMock(return_value=None)), \
         patch("app.api.endpoints.analyze_security", return_value=fake_finding):
        r = client.post(
            "/api/analysis/analyze",
            headers={"Authorization": f"Bearer {mock_token}"},
            json={"repo_url": "https://github.com/octocat/Hello-World", "pr_number": 1},
        )

    finding = r.json()["security_findings"][0]
    assert "ai_explanation" not in finding


def test_analyze_stays_fast_even_when_llm_would_be_extremely_slow():
    """
    Proves the actual point of the split: /analyze must not touch the LLM
    layer at all, so a hanging/slow provider can never affect it - unlike
    before the split, when a single slow LLM call could stall the whole
    analysis response.
    """
    from fastapi.testclient import TestClient
    from app.main import app

    def hanging_post(*args, **kwargs):
        time.sleep(5)
        raise AssertionError("generate_content should never be reached by /analyze")

    with patch("app.api.endpoints.fetch_pr_data", new=AsyncMock(return_value=FAKE_PR_DATA)), \
         patch("app.api.endpoints.fetch_architecture_rules", new=AsyncMock(return_value=None)), \
         patch("requests.post", side_effect=hanging_post):
        with TestClient(app) as client:
            token = client.get("/api/analysis/auth/github/callback?code=mock").json()["access_token"]

            start = time.monotonic()
            r = client.post(
                "/api/analysis/analyze",
                headers={"Authorization": f"Bearer {token}"},
                json={"repo_url": "https://github.com/octocat/Hello-World", "pr_number": 1},
            )
            elapsed = time.monotonic() - start

    assert r.status_code == 200
    assert elapsed < 2.0  # nowhere near the 5s the (unreachable) LLM mock would have taken
