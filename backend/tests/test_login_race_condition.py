from unittest.mock import patch

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core import config
from app.models.pr import SessionLocal, User

# Regression coverage for a real production bug: a fresh user's first
# GitHub login intermittently returned a raw 500 "Internal Server Error"
# (working on retry, once their user row existed). Root cause: github_id
# has a unique constraint, and the callback did a non-atomic
# check-then-insert - two callbacks racing for the same brand-new identity
# could both find "no existing user" and both attempt to insert, and the
# loser's commit raised an unhandled IntegrityError.


class _FakeResponse:
    def __init__(self, json_data):
        self._json_data = json_data

    def json(self):
        return self._json_data


class _FakeAsyncClient:
    def __init__(self, token_response, user_response):
        self._token_response = token_response
        self._user_response = user_response

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, url, data=None, headers=None):
        return self._token_response

    async def get(self, url, headers=None):
        return self._user_response


def _cleanup(github_id):
    db = SessionLocal()
    try:
        db.query(User).filter(User.github_id == github_id).delete()
        db.commit()
    finally:
        db.close()


def test_login_recovers_cleanly_from_a_concurrent_insert_race(client, monkeypatch):
    monkeypatch.setattr(config.settings, "GITHUB_CLIENT_ID", "fake-client-id")
    monkeypatch.setattr(config.settings, "GITHUB_CLIENT_SECRET", "fake-client-secret")

    github_id = "race-condition-test-999999999"

    # No row exists yet, so the endpoint's own check-query correctly finds
    # nothing and takes the insert branch - the race has to happen at
    # commit time, not before, or the test doesn't exercise the same code
    # path a real race would.
    token_response = _FakeResponse({"access_token": "gh-token-abc"})
    user_response = _FakeResponse({"id": github_id, "login": "racer", "avatar_url": "https://example.com/racer.png"})
    fake_client = _FakeAsyncClient(token_response, user_response)

    real_commit = Session.commit
    call_count = {"n": 0}

    def flaky_commit(self):
        call_count["n"] += 1
        if call_count["n"] == 1:
            # Simulate a concurrent callback's insert landing in the
            # database at exactly this moment (via a wholly separate
            # session/connection, standing in for the other request), then
            # this session's own commit losing the unique-constraint race
            # against it.
            winner_db = SessionLocal()
            try:
                winner_db.add(User(
                    github_id=github_id, username="racer",
                    avatar_url="https://example.com/racer.png", email="racer@github.com",
                ))
                winner_db.commit()
            finally:
                winner_db.close()
            raise IntegrityError("INSERT INTO users ...", {}, Exception("duplicate key value violates unique constraint"))
        return real_commit(self)

    try:
        with patch("app.api.endpoints.httpx.AsyncClient", return_value=fake_client), \
             patch("sqlalchemy.orm.Session.commit", flaky_commit):
            r = client.get("/api/analysis/auth/github/callback?code=real-oauth-code-xyz")

        assert r.status_code == 200
        assert "Authentication successful" in r.text
        assert call_count["n"] >= 2  # the failed insert attempt, then the successful retry path

        # No duplicate row - the recovery re-fetched the existing one
        # rather than creating a second.
        db = SessionLocal()
        try:
            matching = db.query(User).filter(User.github_id == github_id).all()
            assert len(matching) == 1
            assert matching[0].username == "racer"
        finally:
            db.close()
    finally:
        _cleanup(github_id)


def test_login_returns_a_clean_error_if_the_row_is_still_missing_after_recovery(client, monkeypatch):
    """
    The genuinely-unexpected case: the constraint fired but even a fresh
    query can't find the row (e.g. the other transaction rolled back too).
    Must not surface a raw unhandled 500 - a clean, actionable JSON error
    instead.
    """
    monkeypatch.setattr(config.settings, "GITHUB_CLIENT_ID", "fake-client-id")
    monkeypatch.setattr(config.settings, "GITHUB_CLIENT_SECRET", "fake-client-secret")

    github_id = "race-condition-test-vanishing-000000"
    token_response = _FakeResponse({"access_token": "gh-token-abc"})
    user_response = _FakeResponse({"id": github_id, "login": "ghost", "avatar_url": "https://example.com/ghost.png"})
    fake_client = _FakeAsyncClient(token_response, user_response)

    def always_raise_on_first_commit(self, _count={"n": 0}):
        _count["n"] += 1
        if _count["n"] == 1:
            raise IntegrityError("INSERT INTO users ...", {}, Exception("duplicate key"))
        # No row was ever actually inserted by anyone else in this test, so
        # the recovery re-query genuinely finds nothing.

    with patch("app.api.endpoints.httpx.AsyncClient", return_value=fake_client), \
         patch("sqlalchemy.orm.Session.commit", always_raise_on_first_commit):
        r = client.get("/api/analysis/auth/github/callback?code=real-oauth-code-abc")

    assert r.status_code == 500
    assert "try logging in again" in r.json()["detail"].lower()
