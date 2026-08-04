import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from app.models.pr import IndexedCall, IndexedFunction, RepoIndex, SessionLocal
from app.services.repo_index_engine import build_or_update_index, enrich_with_repo_wide_blast_radius


@pytest.fixture(autouse=True)
def _clean_repo_index_tables(client):
    # `client` isn't used directly - it's a dependency purely to trigger
    # init_db() (via TestClient's startup event) before these tests touch
    # the tables directly.
    def _clear():
        db = SessionLocal()
        try:
            db.query(IndexedCall).delete()
            db.query(IndexedFunction).delete()
            db.query(RepoIndex).delete()
            db.commit()
        finally:
            db.close()

    _clear()
    yield
    _clear()


def test_full_build_indexes_all_parseable_files_and_skips_others():
    tree = [
        {"path": "app/a.py", "type": "blob"},
        {"path": "app/b.js", "type": "blob"},
        {"path": "README.md", "type": "blob"},
        {"path": "app/subdir", "type": "tree"},  # directories should be ignored
    ]
    contents = {
        "app/a.py": "def helper():\n    return 1\n\ndef main():\n    return helper()\n",
        "app/b.js": "function helper() { return 1; }\nfunction main() { return helper(); }\n",
    }

    async def fake_fetch_file_content(client_, headers, owner, repo, path, ref):
        assert ref == "sha1"
        return contents.get(path)

    with patch("app.services.repo_index_engine.fetch_default_branch_head_sha", new=AsyncMock(return_value=("main", "sha1"))), \
         patch("app.services.repo_index_engine.fetch_repo_tree", new=AsyncMock(return_value=tree)), \
         patch("app.services.repo_index_engine.fetch_file_content", new=fake_fetch_file_content):
        db = SessionLocal()
        try:
            repo_index = asyncio.run(build_or_update_index(db, "octocat", "Hello-World"))
            status, indexed_sha, file_count, function_count, repo_index_id = (
                repo_index.status, repo_index.indexed_sha, repo_index.file_count,
                repo_index.function_count, repo_index.id,
            )
        finally:
            db.close()

    assert status == "ready"
    assert indexed_sha == "sha1"
    assert file_count == 2  # README.md and the directory entry don't count
    assert function_count == 4  # helper + main, in each of 2 files

    db = SessionLocal()
    try:
        calls = db.query(IndexedCall).filter(IndexedCall.repo_index_id == repo_index_id).all()
        assert len(calls) == 2  # main->helper, once per file
        assert {(c.caller_name, c.callee_name) for c in calls} == {("main", "helper")}
    finally:
        db.close()


def test_second_call_with_unchanged_head_sha_is_a_no_op():
    tree = [{"path": "app/a.py", "type": "blob"}]

    async def fake_fetch_file_content(client_, headers, owner, repo, path, ref):
        return "def a():\n    pass\n"

    with patch("app.services.repo_index_engine.fetch_default_branch_head_sha", new=AsyncMock(return_value=("main", "sha1"))), \
         patch("app.services.repo_index_engine.fetch_repo_tree", new=AsyncMock(return_value=tree)) as mock_tree, \
         patch("app.services.repo_index_engine.fetch_file_content", new=fake_fetch_file_content):
        db = SessionLocal()
        try:
            asyncio.run(build_or_update_index(db, "octocat", "Hello-World"))
            asyncio.run(build_or_update_index(db, "octocat", "Hello-World"))
        finally:
            db.close()

    mock_tree.assert_called_once()  # second call short-circuited before touching the tree API


def test_incremental_update_only_reparses_changed_files():
    tree = [
        {"path": "app/a.py", "type": "blob"},
        {"path": "app/b.py", "type": "blob"},
    ]
    v1_contents = {
        "app/a.py": "def a():\n    pass\n",
        "app/b.py": "def b():\n    pass\n",
    }

    async def fake_fetch_v1(client_, headers, owner, repo, path, ref):
        return v1_contents.get(path)

    with patch("app.services.repo_index_engine.fetch_default_branch_head_sha", new=AsyncMock(return_value=("main", "sha1"))), \
         patch("app.services.repo_index_engine.fetch_repo_tree", new=AsyncMock(return_value=tree)), \
         patch("app.services.repo_index_engine.fetch_file_content", new=fake_fetch_v1):
        db = SessionLocal()
        try:
            repo_index = asyncio.run(build_or_update_index(db, "octocat", "Hello-World"))
            function_count = repo_index.function_count
        finally:
            db.close()

    assert function_count == 2

    # Only app/a.py changed (a() -> renamed to a2()); app/b.py is untouched.
    compare_files = [{"filename": "app/a.py", "status": "modified"}]

    async def fake_fetch_v2(client_, headers, owner, repo, path, ref):
        assert path == "app/a.py"  # b.py must never be re-fetched
        return "def a2():\n    pass\n"

    with patch("app.services.repo_index_engine.fetch_default_branch_head_sha", new=AsyncMock(return_value=("main", "sha2"))), \
         patch("app.services.repo_index_engine.fetch_compare", new=AsyncMock(return_value=compare_files)) as mock_compare, \
         patch("app.services.repo_index_engine.fetch_repo_tree", new=AsyncMock(side_effect=AssertionError("full tree fetch should not happen on an incremental update"))), \
         patch("app.services.repo_index_engine.fetch_file_content", new=fake_fetch_v2):
        db = SessionLocal()
        try:
            repo_index = asyncio.run(build_or_update_index(db, "octocat", "Hello-World"))
            indexed_sha, repo_index_id = repo_index.indexed_sha, repo_index.id
        finally:
            db.close()

    mock_compare.assert_called_once_with("octocat", "Hello-World", "sha1", "sha2")
    assert indexed_sha == "sha2"

    db = SessionLocal()
    try:
        names = {f.name for f in db.query(IndexedFunction).filter(IndexedFunction.repo_index_id == repo_index_id).all()}
    finally:
        db.close()
    assert names == {"a2", "b"}  # "a" replaced by "a2"; "b" untouched and still present


def test_incremental_update_removes_entries_for_deleted_files():
    tree = [{"path": "app/a.py", "type": "blob"}]

    async def fake_fetch_v1(client_, headers, owner, repo, path, ref):
        return "def a():\n    pass\n"

    with patch("app.services.repo_index_engine.fetch_default_branch_head_sha", new=AsyncMock(return_value=("main", "sha1"))), \
         patch("app.services.repo_index_engine.fetch_repo_tree", new=AsyncMock(return_value=tree)), \
         patch("app.services.repo_index_engine.fetch_file_content", new=fake_fetch_v1):
        db = SessionLocal()
        try:
            repo_index = asyncio.run(build_or_update_index(db, "octocat", "Hello-World"))
            function_count = repo_index.function_count
        finally:
            db.close()

    assert function_count == 1

    compare_files = [{"filename": "app/a.py", "status": "removed"}]
    with patch("app.services.repo_index_engine.fetch_default_branch_head_sha", new=AsyncMock(return_value=("main", "sha2"))), \
         patch("app.services.repo_index_engine.fetch_compare", new=AsyncMock(return_value=compare_files)):
        db = SessionLocal()
        try:
            repo_index = asyncio.run(build_or_update_index(db, "octocat", "Hello-World"))
            function_count = repo_index.function_count
        finally:
            db.close()

    assert function_count == 0


def test_build_failure_marks_status_failed_and_records_error():
    with patch("app.services.repo_index_engine.fetch_default_branch_head_sha", new=AsyncMock(return_value=("main", "sha1"))), \
         patch("app.services.repo_index_engine.fetch_repo_tree", new=AsyncMock(side_effect=RuntimeError("GitHub API error"))):
        db = SessionLocal()
        try:
            with pytest.raises(RuntimeError):
                asyncio.run(build_or_update_index(db, "octocat", "Hello-World"))
        finally:
            db.close()

    db = SessionLocal()
    try:
        repo_index = db.query(RepoIndex).filter(RepoIndex.repository == "octocat/Hello-World").first()
        status, error_message = repo_index.status, repo_index.error_message
    finally:
        db.close()
    assert status == "failed"
    assert "GitHub API error" in error_message


def test_full_build_respects_the_file_cap(monkeypatch):
    import app.services.repo_index_engine as engine
    monkeypatch.setattr(engine, "MAX_FILES_PER_INDEX", 2)

    tree = [{"path": f"app/f{i}.py", "type": "blob"} for i in range(5)]

    async def fake_fetch(client_, headers, owner, repo, path, ref):
        return "def f():\n    pass\n"

    with patch("app.services.repo_index_engine.fetch_default_branch_head_sha", new=AsyncMock(return_value=("main", "sha1"))), \
         patch("app.services.repo_index_engine.fetch_repo_tree", new=AsyncMock(return_value=tree)), \
         patch("app.services.repo_index_engine.fetch_file_content", new=fake_fetch):
        db = SessionLocal()
        try:
            repo_index = asyncio.run(build_or_update_index(db, "octocat", "Hello-World"))
            file_count = repo_index.file_count
        finally:
            db.close()

    assert file_count == 2


# --- enrich_with_repo_wide_blast_radius ---


def test_enrich_reports_not_indexed_when_no_index_exists():
    dependency_graph = {"modified_functions": [{"function": "main", "calls": [], "called_by": []}], "total_edges": 0}
    db = SessionLocal()
    try:
        enrich_with_repo_wide_blast_radius(db, "octocat", "Hello-World", dependency_graph)
    finally:
        db.close()

    assert dependency_graph["repo_index_status"] == "not_indexed"
    assert "repo_wide_called_by" not in dependency_graph["modified_functions"][0]


def test_enrich_adds_repo_wide_callers_excluding_already_known_local_ones():
    db = SessionLocal()
    try:
        repo_index = RepoIndex(repository="octocat/Hello-World", status="ready", indexed_sha="sha1")
        db.add(repo_index)
        db.commit()
        db.refresh(repo_index)

        db.add(IndexedCall(repo_index_id=repo_index.id, caller_file_path="app/other.py", caller_name="otherCaller", callee_name="target"))
        db.add(IndexedCall(repo_index_id=repo_index.id, caller_file_path="app/local.py", caller_name="localCaller", callee_name="target"))
        db.commit()

        dependency_graph = {
            "modified_functions": [{"function": "target", "calls": [], "called_by": ["localCaller"]}],
            "total_edges": 0,
        }
        enrich_with_repo_wide_blast_radius(db, "octocat", "Hello-World", dependency_graph)
    finally:
        db.close()

    assert dependency_graph["repo_index_status"] == "ready"
    entry = dependency_graph["modified_functions"][0]
    assert entry["repo_wide_called_by"] == ["app/other.py:otherCaller"]


def test_enrich_does_nothing_extra_when_index_exists_but_is_not_ready():
    db = SessionLocal()
    try:
        db.add(RepoIndex(repository="octocat/Hello-World", status="indexing"))
        db.commit()

        dependency_graph = {"modified_functions": [{"function": "main", "calls": [], "called_by": []}], "total_edges": 0}
        enrich_with_repo_wide_blast_radius(db, "octocat", "Hello-World", dependency_graph)
    finally:
        db.close()

    assert dependency_graph["repo_index_status"] == "indexing"
    assert "repo_wide_called_by" not in dependency_graph["modified_functions"][0]
