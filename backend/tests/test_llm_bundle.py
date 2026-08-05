import json
from unittest.mock import MagicMock, patch

from app.services.llm import explain_security_findings_batch, generate_review_bundle

# Regression coverage for the LLM call-merging refactor: checklist,
# comments, executive summary, and Jira context used to be four separate
# LLM calls (plus one per security finding); this collapses them into at
# most 2 total, which is the main lever against exhausting a shared
# free-tier key's quota under real traffic.

BASE_CONTEXT = {
    "pr_type": "BACKEND", "diff_summary": "x", "changed_files": [],
    "risk_score": 5, "risk_category": "Medium", "impact_analysis": {}, "architecture_violations": [],
}


def _success(json_body):
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = json_body
    return resp


def _gemini_text_response(text: str):
    return _success({"candidates": [{"content": {"parts": [{"text": text}]}}]})


class _RateLimitedResponse:
    status_code = 429


# --- generate_review_bundle ---


def test_bundle_parses_all_four_fields_from_one_call():
    bundle_response = {
        "review_checklist": ["Check A", "Check B"],
        "suggested_comments": [
            {"file": "x.py", "issue": "i", "suggestion": "s", "reasoning": "r", "confidence": 90, "severity": "Warning"},
            {"file": "y.py", "issue": "i2", "suggestion": "s2", "reasoning": "r2", "confidence": 50, "severity": "Critical"},
        ],
        "executive_summary": "### Purpose\nx\n\n### Risk\nLow\n\n### Impact\nx\n\n### Recommendation\nx",
        "jira_context": {"Confidence": 70, "Coverage": "2/3", "Missing Requirements": "none"},
    }
    with patch("requests.post", return_value=_gemini_text_response(json.dumps(bundle_response))) as mock_post:
        result = generate_review_bundle(BASE_CONTEXT, {"title": "Fix ABC-123 bug", "description": ""}, api_key="k", provider="gemini")

    assert mock_post.call_count == 1  # the whole point: one call, not four
    assert result["review_checklist"] == ["Check A", "Check B"]
    assert result["suggested_comments"] == [
        {"file": "x.py", "issue": "i", "suggestion": "s", "reasoning": "r", "confidence": 90, "severity": "Warning"}
    ]  # the confidence=50 comment is filtered out
    assert result["executive_summary"].startswith("### Purpose")
    assert result["jira_context"] == {"Ticket": "ABC-123", "Confidence": 70, "Coverage": "2/3", "Missing_Requirements": "none"}


def test_bundle_caps_checklist_and_comments_length():
    bundle_response = {
        "review_checklist": [f"Item {i}" for i in range(8)],
        "suggested_comments": [
            {"file": "f.py", "issue": "i", "suggestion": "s", "reasoning": "r", "confidence": 95, "severity": "Critical"}
            for _ in range(6)
        ],
        "executive_summary": "summary",
        "jira_context": None,
    }
    with patch("requests.post", return_value=_gemini_text_response(json.dumps(bundle_response))):
        result = generate_review_bundle(BASE_CONTEXT, {"title": "no ticket here", "description": ""}, api_key="k", provider="gemini")

    assert len(result["review_checklist"]) == 5
    assert len(result["suggested_comments"]) == 3
    assert result["jira_context"] is None  # no ticket ID in the title/description


def test_bundle_returns_none_jira_when_no_ticket_id_present():
    bundle_response = {"review_checklist": [], "suggested_comments": [], "executive_summary": "s", "jira_context": {"Confidence": 99}}
    with patch("requests.post", return_value=_gemini_text_response(json.dumps(bundle_response))):
        result = generate_review_bundle(BASE_CONTEXT, {"title": "no ticket", "description": "still none"}, api_key="k", provider="gemini")

    # Even though the model returned a jira_context object, there's no real
    # ticket ID in the PR - the function's own regex is authoritative, not
    # whatever the model guessed.
    assert result["jira_context"] is None


def test_bundle_falls_back_to_defaults_when_response_is_not_valid_json():
    with patch("requests.post", return_value=_gemini_text_response("not json at all")):
        result = generate_review_bundle(BASE_CONTEXT, {"title": "ABC-1 ticket", "description": ""}, api_key="k", provider="gemini")

    assert result["review_checklist"] == ["Verify code changes against requirements"]
    assert result["suggested_comments"] == []
    assert "AI Response Could Not Be Parsed" in result["executive_summary"]
    assert result["jira_context"] == {"Ticket": "ABC-1", "Confidence": 80, "Coverage": "N/A", "Missing_Requirements": "None detected"}


def test_bundle_falls_back_with_rate_limit_message_when_call_is_exhausted():
    with patch("requests.post", return_value=_RateLimitedResponse()), patch("app.services.llm.time.sleep"):
        result = generate_review_bundle(BASE_CONTEXT, {"title": "no ticket", "description": ""}, api_key="user-key", provider="gemini")

    assert "Your Gemini API Key Was Rate-Limited" in result["executive_summary"]
    assert result["review_checklist"] == ["Verify code changes against requirements"]
    assert result["suggested_comments"] == []


def test_bundle_only_makes_one_call_regardless_of_provider():
    bundle_response = {"review_checklist": [], "suggested_comments": [], "executive_summary": "s", "jira_context": None}
    with patch("requests.post", return_value=_success({"choices": [{"message": {"content": json.dumps(bundle_response)}}]})) as mock_post:
        generate_review_bundle(BASE_CONTEXT, {"title": "x", "description": ""}, api_key="k", provider="openai")
    assert mock_post.call_count == 1


# --- explain_security_findings_batch ---


def test_batch_explains_all_findings_in_one_call_and_preserves_order():
    findings = [
        {"name": "Hardcoded secret", "severity": "High", "file": "a.py", "snippet": "API_KEY='x'", "reason": "r1", "recommendation": "rec1"},
        {"name": "SQL injection", "severity": "Critical", "file": "b.py", "snippet": "query % x", "reason": "r2", "recommendation": "rec2"},
    ]
    explanations = {"explanations": [
        {"explanation": "exp1", "recommendation": "newrec1", "impact_summary": "impact1"},
        {"explanation": "exp2", "recommendation": "newrec2", "impact_summary": "impact2"},
    ]}
    with patch("requests.post", return_value=_gemini_text_response(json.dumps(explanations))) as mock_post:
        result = explain_security_findings_batch(findings, api_key="k", provider="gemini")

    assert mock_post.call_count == 1  # one call for N findings, not N calls
    assert result[0]["name"] == "Hardcoded secret"
    assert result[0]["ai_explanation"] == "exp1"
    assert result[0]["ai_recommendation"] == "newrec1"
    assert result[1]["name"] == "SQL injection"
    assert result[1]["ai_explanation"] == "exp2"


def test_batch_returns_findings_unchanged_on_length_mismatch():
    findings = [{"name": "A", "severity": "High", "file": "a.py", "snippet": "x", "reason": "r", "recommendation": "rec"}]
    # Model returns 2 explanations for 1 finding - untrustworthy, don't guess which maps to which.
    mismatched = {"explanations": [{"explanation": "e1"}, {"explanation": "e2"}]}
    with patch("requests.post", return_value=_gemini_text_response(json.dumps(mismatched))):
        result = explain_security_findings_batch(findings, api_key="k", provider="gemini")

    assert result == findings
    assert "ai_explanation" not in result[0]


def test_batch_returns_findings_unchanged_when_explanations_key_is_missing():
    findings = [{"name": "A", "severity": "High", "file": "a.py", "snippet": "x", "reason": "r", "recommendation": "rec"}]
    # A valid JSON object, but not shaped as {"explanations": [...]}.
    with patch("requests.post", return_value=_gemini_text_response(json.dumps({"foo": "bar"}))):
        result = explain_security_findings_batch(findings, api_key="k", provider="gemini")
    assert result == findings


def test_batch_returns_findings_unchanged_when_response_is_not_json():
    findings = [{"name": "A", "severity": "High", "file": "a.py", "snippet": "x", "reason": "r", "recommendation": "rec"}]
    with patch("requests.post", return_value=_gemini_text_response("not json")):
        result = explain_security_findings_batch(findings, api_key="k", provider="gemini")
    assert result == findings


def test_batch_makes_no_call_at_all_for_an_empty_findings_list():
    with patch("requests.post") as mock_post:
        result = explain_security_findings_batch([], api_key="k", provider="gemini")
    assert result == []
    assert not mock_post.called
