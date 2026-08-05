from unittest.mock import AsyncMock, patch

import app.api.endpoints as endpoints_module

# Regression coverage: analyze_security has no cap on how many findings it
# can return, so without a cap here, a messy PR could send an unbounded
# number of findings into the single batch-explanation prompt.

FAKE_PR_DATA = {
    "owner": "octocat", "repo": "Hello-World", "number": 1,
    "title": "Test PR", "description": "", "additions": 10, "deletions": 2,
    "changed_files": 1, "files": [{"filename": "x.py", "patch": "+print('hi')"}],
}


def test_only_the_first_N_findings_are_sent_for_ai_explanation(client, mock_token):
    fake_findings = [
        {"name": f"Finding {i}", "severity": "High", "file": "x.py",
         "confidence": 95, "reason": "x", "recommendation": "x", "snippet": "x"}
        for i in range(15)
    ]

    def fake_batch_explain(findings, api_key, provider):
        # Echo back which findings were actually sent, tagged, so the test
        # can assert on count and on which ones got the AI treatment.
        return [{**f, "ai_explanation": "explained"} for f in findings]

    with patch("app.api.endpoints.fetch_pr_data", new=AsyncMock(return_value=FAKE_PR_DATA)), \
         patch("app.api.endpoints.fetch_architecture_rules", new=AsyncMock(return_value=None)), \
         patch("app.api.endpoints.analyze_security", return_value=fake_findings), \
         patch("app.api.endpoints.explain_security_findings_batch", side_effect=fake_batch_explain) as mock_batch, \
         patch("app.api.endpoints.generate_review_bundle", return_value={
             "review_checklist": [], "suggested_comments": [], "executive_summary": "", "jira_context": None,
         }), \
         patch("app.api.endpoints.asyncio.sleep", return_value=None):
        r = client.post(
            "/api/analysis/analyze/enrich",
            headers={"Authorization": f"Bearer {mock_token}"},
            json={"repo_url": "https://github.com/octocat/Hello-World", "pr_number": 1},
        )

    assert r.status_code == 200
    body = r.json()
    assert len(body["security_findings"]) == 15  # all findings still surface

    # explain_security_findings_batch is called exactly once, with only the
    # first MAX_AI_EXPLAINED_FINDINGS findings.
    mock_batch.assert_called_once()
    sent_findings = mock_batch.call_args[0][0]
    assert len(sent_findings) == endpoints_module.MAX_AI_EXPLAINED_FINDINGS

    explained_count = sum(1 for f in body["security_findings"] if f.get("ai_explanation") == "explained")
    assert explained_count == endpoints_module.MAX_AI_EXPLAINED_FINDINGS


def test_no_findings_means_no_batch_explanation_call(client, mock_token):
    with patch("app.api.endpoints.fetch_pr_data", new=AsyncMock(return_value=FAKE_PR_DATA)), \
         patch("app.api.endpoints.fetch_architecture_rules", new=AsyncMock(return_value=None)), \
         patch("app.api.endpoints.analyze_security", return_value=[]), \
         patch("app.api.endpoints.explain_security_findings_batch") as mock_batch, \
         patch("app.api.endpoints.generate_review_bundle", return_value={
             "review_checklist": [], "suggested_comments": [], "executive_summary": "", "jira_context": None,
         }), \
         patch("app.api.endpoints.asyncio.sleep", return_value=None):
        r = client.post(
            "/api/analysis/analyze/enrich",
            headers={"Authorization": f"Bearer {mock_token}"},
            json={"repo_url": "https://github.com/octocat/Hello-World", "pr_number": 1},
        )

    assert r.status_code == 200
    mock_batch.assert_called_once_with([], None, "gemini")
