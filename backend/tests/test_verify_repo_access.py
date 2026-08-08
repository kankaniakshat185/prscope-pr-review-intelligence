import asyncio
from unittest.mock import patch

from app.services.github import verify_repo_access


class _FakeResponse:
    def __init__(self, status_code=200, json_data=None):
        self.status_code = status_code
        self._json_data = json_data or {}

    def json(self):
        return self._json_data


class _FakeAsyncClient:
    def __init__(self, responder):
        self._responder = responder

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    async def get(self, url, headers=None):
        return self._responder(url, headers)


def _patch_client(responder):
    return patch("app.services.github.httpx.AsyncClient", return_value=_FakeAsyncClient(responder))


def test_private_repo_any_successful_fetch_grants_access():
    # GitHub 404s a private repo for non-collaborators - a 200 with
    # private=True already proves the token's owner is a real collaborator.
    with _patch_client(lambda url, headers: _FakeResponse(200, {"private": True})):
        assert asyncio.run(verify_repo_access("acme", "internal-repo", "tok")) is True


def test_private_repo_404_denies_access():
    with _patch_client(lambda url, headers: _FakeResponse(404)):
        assert asyncio.run(verify_repo_access("acme", "internal-repo", "tok")) is False


def test_public_repo_with_push_permission_grants_access():
    with _patch_client(lambda url, headers: _FakeResponse(200, {"private": False, "permissions": {"pull": True, "push": True}})):
        assert asyncio.run(verify_repo_access("acme", "public-repo", "tok")) is True


def test_public_repo_with_admin_permission_grants_access():
    with _patch_client(lambda url, headers: _FakeResponse(200, {"private": False, "permissions": {"pull": True, "push": False, "admin": True}})):
        assert asyncio.run(verify_repo_access("acme", "public-repo", "tok")) is True


def test_public_repo_read_only_denies_access():
    # This is the whole point: read access to a public repo is universal
    # and must NOT be treated as proof of real team membership.
    with _patch_client(lambda url, headers: _FakeResponse(200, {"private": False, "permissions": {"pull": True, "push": False}})):
        assert asyncio.run(verify_repo_access("acme", "public-repo", "tok")) is False


def test_public_repo_with_no_permissions_field_denies_access():
    with _patch_client(lambda url, headers: _FakeResponse(200, {"private": False})):
        assert asyncio.run(verify_repo_access("acme", "public-repo", "tok")) is False


def test_no_token_denies_access_without_making_a_request():
    with patch("app.services.github.httpx.AsyncClient") as mock_client_cls:
        assert asyncio.run(verify_repo_access("acme", "repo", "")) is False
    mock_client_cls.assert_not_called()


def test_network_error_denies_access_rather_than_raising():
    import httpx

    class _FailingClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url, headers=None):
            raise httpx.ConnectError("boom")

    with patch("app.services.github.httpx.AsyncClient", return_value=_FailingClient()):
        assert asyncio.run(verify_repo_access("acme", "repo", "tok")) is False
