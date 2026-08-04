import hashlib
import hmac
import json

from app.core import config


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
