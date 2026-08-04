from app.core import config


def test_analyze_requires_auth(client):
    r = client.post("/api/analysis/analyze", json={"repo_url": "https://github.com/x/y", "pr_number": 1})
    assert r.status_code == 403


def test_analyze_rejects_invalid_token(client):
    r = client.post(
        "/api/analysis/analyze",
        headers={"Authorization": "Bearer garbage"},
        json={"repo_url": "https://github.com/x/y", "pr_number": 1},
    )
    assert r.status_code == 401


def test_mock_login_issues_a_token_when_enabled(client, mock_token):
    assert mock_token


def test_mock_login_is_rejected_when_disabled(client, monkeypatch):
    monkeypatch.setattr(config.settings, "ENABLE_MOCK_AUTH", False)
    r = client.get("/api/analysis/auth/github/callback?code=mock")
    assert r.status_code == 403


def test_login_endpoint_refuses_to_offer_mock_url_when_disabled_and_unconfigured(client, monkeypatch):
    monkeypatch.setattr(config.settings, "ENABLE_MOCK_AUTH", False)
    monkeypatch.setattr(config.settings, "GITHUB_CLIENT_ID", "")
    r = client.get("/api/analysis/auth/github/login")
    assert r.status_code == 503


def test_saved_reviews_require_auth(client):
    r = client.get("/api/analysis/workspace/reviews")
    assert r.status_code == 403
