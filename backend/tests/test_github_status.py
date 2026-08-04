import asyncio
import pytest
from unittest.mock import patch

from app.services.github_status import post_commit_status


class _FakeResponse:
    def __init__(self, status_code=201, json_data=None):
        self.status_code = status_code
        self._json_data = json_data or {}

    def json(self):
        return self._json_data

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class _FakeAsyncClient:
    def __init__(self, responder, calls):
        self._responder = responder
        self._calls = calls

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def post(self, url, headers=None, json=None):
        self._calls.append((url, headers, json))
        return self._responder(url, headers, json)


def _patch_client(responder, calls):
    return patch("app.services.github_status.httpx.AsyncClient", return_value=_FakeAsyncClient(responder, calls))


def test_posts_to_the_statuses_api_with_expected_payload():
    calls = []

    def responder(url, headers, json_body):
        assert url == "https://api.github.com/repos/octocat/Hello-World/statuses/abc123"
        assert headers["Authorization"] == "Bearer user-pat"
        assert json_body["state"] == "success"
        assert json_body["context"] == "prscope/risk-review"
        return _FakeResponse(201, {"id": 1, "state": "success", "created_at": "2024-01-01T00:00:00Z"})

    with _patch_client(responder, calls):
        result = asyncio.run(post_commit_status(
            repo_url="https://github.com/octocat/Hello-World",
            sha="abc123",
            state="success",
            description="Low risk (2/10), no security findings",
            github_token="user-pat",
        ))

    assert result == {"status_id": 1, "state": "success", "created_at": "2024-01-01T00:00:00Z"}
    assert len(calls) == 1


def test_falls_back_to_shared_token_when_no_user_token_given():
    calls = []

    def responder(url, headers, json_body):
        assert headers["Authorization"] == "Bearer shared-token"
        return _FakeResponse(201, {"id": 2, "state": "failure"})

    with patch("app.services.github_status.settings.GITHUB_TOKEN", "shared-token"), _patch_client(responder, calls):
        asyncio.run(post_commit_status(
            repo_url="https://github.com/octocat/Hello-World",
            sha="abc123",
            state="failure",
            description="High risk",
        ))

    assert len(calls) == 1


def test_raises_when_no_token_available_anywhere():
    with patch("app.services.github_status.settings.GITHUB_TOKEN", ""):
        with pytest.raises(ValueError, match="GitHub token is required"):
            asyncio.run(post_commit_status(
                repo_url="https://github.com/octocat/Hello-World",
                sha="abc123",
                state="success",
                description="x",
            ))


def test_rejects_an_invalid_state_before_making_any_request():
    with pytest.raises(ValueError, match="Invalid status state"):
        asyncio.run(post_commit_status(
            repo_url="https://github.com/octocat/Hello-World",
            sha="abc123",
            state="approved",  # not a real GitHub status state
            description="x",
            github_token="tok",
        ))


def test_truncates_description_to_github_140_char_limit():
    calls = []
    long_description = "x" * 500

    def responder(url, headers, json_body):
        assert len(json_body["description"]) == 140
        return _FakeResponse(201, {"id": 3, "state": "success"})

    with _patch_client(responder, calls):
        asyncio.run(post_commit_status(
            repo_url="https://github.com/octocat/Hello-World",
            sha="abc123",
            state="success",
            description=long_description,
            github_token="tok",
        ))


def test_includes_target_url_only_when_provided():
    calls = []

    def responder(url, headers, json_body):
        assert "target_url" not in json_body
        return _FakeResponse(201, {"id": 4, "state": "success"})

    with _patch_client(responder, calls):
        asyncio.run(post_commit_status(
            repo_url="https://github.com/octocat/Hello-World",
            sha="abc123",
            state="success",
            description="x",
            github_token="tok",
        ))
