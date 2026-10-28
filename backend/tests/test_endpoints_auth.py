from app.core import config
from app.services.auth import create_oauth_state


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


def test_login_endpoint_embeds_a_state_param_in_the_redirect_url(client, monkeypatch):
    monkeypatch.setattr(config.settings, "GITHUB_CLIENT_ID", "fake-client-id")
    r = client.get("/api/analysis/auth/github/login")
    assert r.status_code == 200
    assert "&state=" in r.json()["url"]


def test_login_endpoint_only_embeds_an_allow_listed_origin(client, monkeypatch):
    from app.services.auth import verify_oauth_state

    monkeypatch.setattr(config.settings, "GITHUB_CLIENT_ID", "fake-client-id")
    allowed = config.settings.ALLOWED_ORIGINS.split(",")[0].strip()

    r_allowed = client.get("/api/analysis/auth/github/login", headers={"Origin": allowed})
    state = r_allowed.json()["url"].split("state=")[1]
    assert verify_oauth_state(state) == allowed

    r_untrusted = client.get("/api/analysis/auth/github/login", headers={"Origin": "https://evil.example.com"})
    state = r_untrusted.json()["url"].split("state=")[1]
    assert verify_oauth_state(state) == ""


def test_callback_rejects_a_real_oauth_code_with_no_state(client, monkeypatch):
    monkeypatch.setattr(config.settings, "GITHUB_CLIENT_ID", "fake-client-id")
    monkeypatch.setattr(config.settings, "GITHUB_CLIENT_SECRET", "fake-client-secret")
    r = client.get("/api/analysis/auth/github/callback?code=some-code")
    assert r.status_code == 400


def test_callback_rejects_a_forged_or_tampered_state(client, monkeypatch):
    monkeypatch.setattr(config.settings, "GITHUB_CLIENT_ID", "fake-client-id")
    monkeypatch.setattr(config.settings, "GITHUB_CLIENT_SECRET", "fake-client-secret")
    r = client.get("/api/analysis/auth/github/callback?code=some-code&state=not-a-real-token")
    assert r.status_code == 400


def test_callback_rejects_an_expired_state(client, monkeypatch):
    monkeypatch.setattr(config.settings, "GITHUB_CLIENT_ID", "fake-client-id")
    monkeypatch.setattr(config.settings, "GITHUB_CLIENT_SECRET", "fake-client-secret")
    monkeypatch.setattr("app.services.auth.OAUTH_STATE_TTL_SECONDS", -1)
    expired_state = create_oauth_state("")
    r = client.get(f"/api/analysis/auth/github/callback?code=some-code&state={expired_state}")
    assert r.status_code == 400


def test_saved_reviews_require_auth(client):
    r = client.get("/api/analysis/workspace/reviews")
    assert r.status_code == 403


def test_post_comment_requires_auth(client):
    r = client.post("/api/analysis/post-comment", json={"repo_url": "https://github.com/x/y", "pr_number": 1, "comment_body": "hi"})
    assert r.status_code == 403


def test_post_status_requires_auth(client):
    r = client.post(
        "/api/analysis/post-status",
        json={"repo_url": "https://github.com/x/y", "pr_number": 1, "state": "success", "description": "d"},
    )
    assert r.status_code == 403
