from unittest.mock import AsyncMock, patch

import pytest


@pytest.fixture(autouse=True)
def _reset_index_builds_in_progress():
    from app.api import endpoints
    endpoints._index_builds_in_progress.clear()
    yield
    endpoints._index_builds_in_progress.clear()


def test_index_build_requires_auth(client):
    r = client.post("/api/analysis/index/build", json={"repo_url": "https://github.com/o/r"})
    assert r.status_code == 403


def test_index_status_requires_auth(client):
    r = client.get("/api/analysis/index/status", params={"repo_url": "https://github.com/o/r"})
    assert r.status_code == 403


def test_index_status_reports_not_indexed_by_default(client, mock_token):
    r = client.get(
        "/api/analysis/index/status",
        headers={"Authorization": f"Bearer {mock_token}"},
        params={"repo_url": "https://github.com/octocat/never-indexed-repo"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "not_indexed"
    assert body["repository"] == "octocat/never-indexed-repo"


def test_index_build_kicks_off_a_background_task_and_returns_started(client, mock_token):
    with patch("app.api.endpoints.build_or_update_index", new=AsyncMock(return_value=None)):
        r = client.post(
            "/api/analysis/index/build",
            headers={"Authorization": f"Bearer {mock_token}"},
            json={"repo_url": "https://github.com/octocat/build-test-repo"},
        )

    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "started"
    assert body["repository"] == "octocat/build-test-repo"


def test_index_build_reports_already_in_progress_for_a_duplicate_call(client, mock_token):
    from app.api import endpoints
    endpoints._index_builds_in_progress.add("octocat/dup-repo")

    r = client.post(
        "/api/analysis/index/build",
        headers={"Authorization": f"Bearer {mock_token}"},
        json={"repo_url": "https://github.com/octocat/dup-repo"},
    )

    assert r.status_code == 200
    assert r.json()["status"] == "already_in_progress"


def test_index_build_rejects_a_malformed_repo_url(client, mock_token):
    r = client.post(
        "/api/analysis/index/build",
        headers={"Authorization": f"Bearer {mock_token}"},
        json={"repo_url": "not-a-url"},
    )
    assert r.status_code == 400
