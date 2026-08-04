from unittest.mock import AsyncMock, patch

from app.models.pr import IndexedCall, RepoIndex, SessionLocal


def _make_pr_data(owner: str, repo: str) -> dict:
    return {
        "owner": owner, "repo": repo, "number": 1, "title": "t", "description": "",
        "additions": 1, "deletions": 0, "changed_files": 1,
        "files": [{"filename": "x.py", "patch": "+def main():\n+    pass", "status": "modified"}],
    }


def test_analyze_reports_not_indexed_when_no_index_exists_for_the_repo(client, mock_token):
    pr_data = _make_pr_data("octocat", "no-index-repo")
    with patch("app.api.endpoints.fetch_pr_data", new=AsyncMock(return_value=pr_data)), \
         patch("app.api.endpoints.fetch_architecture_rules", new=AsyncMock(return_value=None)):
        r = client.post(
            "/api/analysis/analyze",
            headers={"Authorization": f"Bearer {mock_token}"},
            json={"repo_url": "https://github.com/octocat/no-index-repo", "pr_number": 1},
        )

    assert r.status_code == 200
    graph = r.json()["impact_analysis"]["dependency_graph"]
    assert graph["repo_index_status"] == "not_indexed"


def test_analyze_surfaces_repo_wide_callers_and_rescues_an_otherwise_filtered_function(client, mock_token):
    # "main" has no calls/called_by within the PR's own changed files (the
    # patch defines it but nothing in-PR calls it), so without repo-wide
    # enrichment it would be filtered out of modified_functions entirely.
    # A repo-wide caller found via the persisted index should both appear
    # AND be enough to keep "main" from being filtered out.
    repository = "acme/widget-repo-index-test"
    db = SessionLocal()
    try:
        repo_index = RepoIndex(repository=repository, status="ready", indexed_sha="sha1")
        db.add(repo_index)
        db.commit()
        db.refresh(repo_index)
        db.add(IndexedCall(
            repo_index_id=repo_index.id, caller_file_path="other/caller.py",
            caller_name="callerFn", callee_name="main",
        ))
        db.commit()
        repo_index_id = repo_index.id
    finally:
        db.close()

    try:
        pr_data = _make_pr_data("acme", "widget-repo-index-test")
        with patch("app.api.endpoints.fetch_pr_data", new=AsyncMock(return_value=pr_data)), \
             patch("app.api.endpoints.fetch_architecture_rules", new=AsyncMock(return_value=None)):
            r = client.post(
                "/api/analysis/analyze",
                headers={"Authorization": f"Bearer {mock_token}"},
                json={"repo_url": f"https://github.com/{repository}", "pr_number": 1},
            )

        assert r.status_code == 200
        graph = r.json()["impact_analysis"]["dependency_graph"]
        assert graph["repo_index_status"] == "ready"

        main_entry = next((f for f in graph["modified_functions"] if f["function"] == "main"), None)
        assert main_entry is not None, "main should survive filtering thanks to its repo-wide caller"
        assert main_entry["repo_wide_called_by"] == ["other/caller.py:callerFn"]
        assert main_entry["called_by"] == []  # nothing local calls it
    finally:
        db = SessionLocal()
        try:
            db.query(IndexedCall).filter(IndexedCall.repo_index_id == repo_index_id).delete()
            db.query(RepoIndex).filter(RepoIndex.id == repo_index_id).delete()
            db.commit()
        finally:
            db.close()
