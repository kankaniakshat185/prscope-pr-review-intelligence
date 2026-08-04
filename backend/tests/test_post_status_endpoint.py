from unittest.mock import AsyncMock, patch


def test_post_status_fetches_head_sha_and_publishes(client, mock_token):
    with patch("app.api.endpoints.fetch_pr_head_sha", new=AsyncMock(return_value="deadbeef")), \
         patch("app.api.endpoints.post_commit_status", new=AsyncMock(return_value={"status_id": 1, "state": "success", "created_at": "now"})) as mock_post:
        r = client.post(
            "/api/analysis/post-status",
            headers={"Authorization": f"Bearer {mock_token}"},
            json={
                "repo_url": "https://github.com/octocat/Hello-World",
                "pr_number": 1,
                "state": "success",
                "description": "Low risk",
                "github_token": "user-pat",
            },
        )

    assert r.status_code == 200
    assert r.json() == {"status_id": 1, "state": "success", "created_at": "now"}
    _, kwargs = mock_post.call_args
    assert kwargs["sha"] == "deadbeef"
    assert kwargs["state"] == "success"
    assert kwargs["description"] == "Low risk"
    assert kwargs["github_token"] == "user-pat"


def test_post_status_returns_500_when_no_github_token_available(client, mock_token):
    with patch("app.api.endpoints.fetch_pr_head_sha", new=AsyncMock(return_value="deadbeef")), \
         patch("app.api.endpoints.post_commit_status", new=AsyncMock(side_effect=ValueError("GitHub token is required to publish a status."))):
        r = client.post(
            "/api/analysis/post-status",
            headers={"Authorization": f"Bearer {mock_token}"},
            json={
                "repo_url": "https://github.com/octocat/Hello-World",
                "pr_number": 1,
                "state": "success",
                "description": "Low risk",
            },
        )

    assert r.status_code == 500
    assert "GitHub token is required" in r.json()["detail"]
