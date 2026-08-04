from unittest.mock import AsyncMock, patch

import app.api.endpoints as endpoints_module

# Regression coverage: analyze_security has no cap on how many findings it
# can return, so without a cap here, a messy PR could trigger dozens of
# AI-explanation calls and blow past any reasonable analysis time budget.

FAKE_PR_DATA = {
    "owner": "octocat", "repo": "Hello-World", "number": 1,
    "title": "Test PR", "description": "", "additions": 10, "deletions": 2,
    "changed_files": 1, "files": [{"filename": "x.py", "patch": "+print('hi')"}],
}


def test_only_the_first_N_findings_get_ai_explained(client, mock_token):
    fake_findings = [
        {"name": f"Finding {i}", "severity": "High", "file": "x.py",
         "confidence": 95, "reason": "x", "recommendation": "x", "snippet": "x"}
        for i in range(15)
    ]
    call_count = {"n": 0}

    def counting_explain(finding, api_key, provider):
        call_count["n"] += 1
        return finding

    def fake_llm_response(*args, **kwargs):
        class Resp:
            status_code = 200
            def json(self):
                return {"candidates": [{"content": {"parts": [{"text": "[]"}]}}]}
        return Resp()

    with patch("app.api.endpoints.fetch_pr_data", new=AsyncMock(return_value=FAKE_PR_DATA)), \
         patch("app.api.endpoints.fetch_architecture_rules", new=AsyncMock(return_value=None)), \
         patch("app.api.endpoints.analyze_security", return_value=fake_findings), \
         patch("app.api.endpoints.explain_security_finding", side_effect=counting_explain), \
         patch("app.api.endpoints.asyncio.sleep", return_value=None), \
         patch("app.services.llm.settings.GEMINI_API_KEY", "fake-key"), \
         patch("requests.post", side_effect=fake_llm_response):
        # AI-explanation of findings now happens in the enrichment endpoint,
        # not the fast deterministic /analyze endpoint.
        r = client.post(
            "/api/analysis/analyze/enrich",
            headers={"Authorization": f"Bearer {mock_token}"},
            json={"repo_url": "https://github.com/octocat/Hello-World", "pr_number": 1},
        )

    assert r.status_code == 200
    body = r.json()
    assert len(body["security_findings"]) == 15  # all findings still surface
    assert call_count["n"] == endpoints_module.MAX_AI_EXPLAINED_FINDINGS  # but only the capped number get AI treatment
