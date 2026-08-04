import asyncio
import hashlib
import hmac
import json
import time
from unittest.mock import AsyncMock, patch

from app.core import config


def _wait_until(predicate, timeout=5.0, interval=0.02):
    """
    Polls for a condition instead of a single fixed sleep - the debounced
    task runs the real deterministic pipeline (minus the two things we mock
    out), and its first run in a test session pays a one-off cold-start cost
    (e.g. the incident-similarity embedding model) that a short fixed sleep
    isn't reliably longer than.
    """
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return predicate()


def test_webhook_rejects_when_secret_unconfigured(client, monkeypatch):
    monkeypatch.setattr(config.settings, "GITHUB_WEBHOOK_SECRET", "")
    r = client.post("/api/analysis/webhook/github", content=b"{}")
    assert r.status_code == 503


def test_webhook_rejects_missing_signature(client, monkeypatch):
    monkeypatch.setattr(config.settings, "GITHUB_WEBHOOK_SECRET", "shh")
    r = client.post("/api/analysis/webhook/github", content=b"{}")
    assert r.status_code == 401


def test_webhook_rejects_wrong_signature(client, monkeypatch):
    monkeypatch.setattr(config.settings, "GITHUB_WEBHOOK_SECRET", "shh")
    body = b'{"action": "opened"}'
    bad_sig = "sha256=" + hmac.new(b"nope", body, hashlib.sha256).hexdigest()
    r = client.post("/api/analysis/webhook/github", content=body, headers={"X-Hub-Signature-256": bad_sig})
    assert r.status_code == 401


def test_webhook_accepts_correctly_signed_payload(client, monkeypatch):
    monkeypatch.setattr(config.settings, "GITHUB_WEBHOOK_SECRET", "shh")
    body = json.dumps({
        "action": "opened",
        "pull_request": {"number": 1},
        "repository": {"owner": {"login": "o"}, "name": "r"},
    }).encode()
    sig = "sha256=" + hmac.new(b"shh", body, hashlib.sha256).hexdigest()
    r = client.post("/api/analysis/webhook/github", content=body, headers={"X-Hub-Signature-256": sig})
    assert r.status_code == 200
    assert r.json() == {"status": "received"}


def _signed_synchronize_body(secret: bytes = b"shh"):
    body = json.dumps({
        "action": "synchronize",
        "pull_request": {"number": 1},
        "repository": {"owner": {"login": "o"}, "name": "r", "html_url": "https://github.com/o/r"},
    }).encode()
    sig = "sha256=" + hmac.new(secret, body, hashlib.sha256).hexdigest()
    return body, sig


def test_webhook_dispatches_debounced_analysis_and_publishes_a_commit_status(client, monkeypatch):
    from app.api import endpoints

    monkeypatch.setattr(config.settings, "GITHUB_WEBHOOK_SECRET", "shh")
    monkeypatch.setattr(endpoints.webhook_debouncer, "delay_seconds", 0.05)

    fake_pr_data = {
        "owner": "o", "repo": "r", "number": 1, "title": "t", "description": "",
        "additions": 1, "deletions": 0, "changed_files": 0,
        "files": [], "head_sha": "abc123", "base_sha": "def456",
    }

    with patch("app.api.endpoints.fetch_pr_data", new=AsyncMock(return_value=fake_pr_data)), \
         patch("app.api.endpoints.fetch_architecture_rules", new=AsyncMock(return_value=None)), \
         patch("app.api.endpoints.post_commit_status", new=AsyncMock(return_value={"status_id": 1})) as mock_post_status:

        body, sig = _signed_synchronize_body()
        r = client.post("/api/analysis/webhook/github", content=body, headers={"X-Hub-Signature-256": sig})
        assert r.status_code == 200

        assert _wait_until(lambda: mock_post_status.called)

    mock_post_status.assert_called_once()
    _, kwargs = mock_post_status.call_args
    assert kwargs["sha"] == "abc123"
    assert kwargs["state"] == "success"  # empty diff -> no risk signals


def test_webhook_coalesces_rapid_synchronize_events_into_one_analysis(client, monkeypatch):
    from app.api import endpoints

    monkeypatch.setattr(config.settings, "GITHUB_WEBHOOK_SECRET", "shh")
    monkeypatch.setattr(endpoints.webhook_debouncer, "delay_seconds", 0.1)

    fake_pr_data = {
        "owner": "o", "repo": "r", "number": 1, "title": "t", "description": "",
        "additions": 1, "deletions": 0, "changed_files": 0,
        "files": [], "head_sha": "abc123", "base_sha": "def456",
    }

    with patch("app.api.endpoints.fetch_pr_data", new=AsyncMock(return_value=fake_pr_data)) as mock_fetch, \
         patch("app.api.endpoints.fetch_architecture_rules", new=AsyncMock(return_value=None)), \
         patch("app.api.endpoints.post_commit_status", new=AsyncMock(return_value={"status_id": 1})) as mock_post_status:

        for _ in range(3):
            body, sig = _signed_synchronize_body()
            r = client.post("/api/analysis/webhook/github", content=body, headers={"X-Hub-Signature-256": sig})
            assert r.status_code == 200
            time.sleep(0.02)  # each new event arrives well within the debounce window

        assert _wait_until(lambda: mock_post_status.called)

    mock_fetch.assert_called_once()
