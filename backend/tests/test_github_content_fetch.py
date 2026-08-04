import asyncio
from unittest.mock import patch

from app.services.github import fetch_pr_data, MAX_FILES_FOR_CONTENT_FETCH


class _FakeResponse:
    def __init__(self, status_code=200, json_data=None, text=""):
        self.status_code = status_code
        self._json_data = json_data
        self.text = text

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

    async def get(self, url, headers=None, params=None):
        self._calls.append((url, headers, params))
        return self._responder(url, headers, params)


def _patch_client(responder, calls):
    return patch("app.services.github.httpx.AsyncClient", return_value=_FakeAsyncClient(responder, calls))


def _pr_info(base_sha="base123", head_sha="head123"):
    return _FakeResponse(200, json_data={
        "title": "t", "body": "d", "additions": 1, "deletions": 1, "changed_files": 1,
        "base": {"sha": base_sha}, "head": {"sha": head_sha},
    })


def test_attaches_base_and_head_content_for_python_files_only():
    def responder(url, headers, params):
        if url.endswith("/pulls/1/files"):
            return _FakeResponse(200, json_data=[
                {"filename": "app/a.py", "status": "modified", "patch": "x"},
                {"filename": "README.md", "status": "modified", "patch": "x"},
            ])
        if url.endswith("/pulls/1"):
            return _pr_info()
        if url.endswith("/contents/app/a.py"):
            ref = params.get("ref")
            return _FakeResponse(200, text="def old(): pass" if ref == "base123" else "def new(): pass")
        raise AssertionError(f"unexpected url {url} params={params}")

    calls = []
    with _patch_client(responder, calls):
        result = asyncio.run(fetch_pr_data("https://github.com/octocat/Hello-World", 1))

    py_file = next(f for f in result["files"] if f["filename"] == "app/a.py")
    assert py_file["base_content"] == "def old(): pass"
    assert py_file["head_content"] == "def new(): pass"

    md_file = next(f for f in result["files"] if f["filename"] == "README.md")
    assert "base_content" not in md_file  # never fetched - not a Python file


def test_uses_raw_accept_header_for_content_requests():
    def responder(url, headers, params):
        if url.endswith("/pulls/1/files"):
            return _FakeResponse(200, json_data=[{"filename": "a.py", "status": "modified", "patch": "x"}])
        if url.endswith("/pulls/1"):
            return _pr_info()
        if url.endswith("/contents/a.py"):
            assert headers["Accept"] == "application/vnd.github.v3.raw"
            return _FakeResponse(200, text="def f(): pass")
        raise AssertionError(f"unexpected url {url}")

    calls = []
    with _patch_client(responder, calls):
        asyncio.run(fetch_pr_data("https://github.com/octocat/Hello-World", 1))


def test_added_file_skips_base_fetch_removed_file_skips_head_fetch():
    contents_calls = []

    def responder(url, headers, params):
        if url.endswith("/pulls/1/files"):
            return _FakeResponse(200, json_data=[
                {"filename": "new.py", "status": "added", "patch": "x"},
                {"filename": "gone.py", "status": "removed", "patch": "x"},
            ])
        if url.endswith("/pulls/1"):
            return _pr_info()
        if "/contents/" in url:
            contents_calls.append((url, params.get("ref")))
            return _FakeResponse(200, text="content")
        raise AssertionError(f"unexpected url {url}")

    calls = []
    with _patch_client(responder, calls):
        result = asyncio.run(fetch_pr_data("https://github.com/octocat/Hello-World", 1))

    new_file = next(f for f in result["files"] if f["filename"] == "new.py")
    gone_file = next(f for f in result["files"] if f["filename"] == "gone.py")
    assert new_file["base_content"] is None  # added file has no base version
    assert new_file["head_content"] == "content"
    assert gone_file["head_content"] is None  # removed file has no head version
    assert gone_file["base_content"] == "content"

    # Only the sides that could plausibly exist were actually requested.
    assert ("https://api.github.com/repos/octocat/Hello-World/contents/new.py", "head123") in contents_calls
    assert ("https://api.github.com/repos/octocat/Hello-World/contents/gone.py", "base123") in contents_calls
    assert len(contents_calls) == 2


def test_content_fetch_returns_none_on_404_without_raising():
    def responder(url, headers, params):
        if url.endswith("/pulls/1/files"):
            return _FakeResponse(200, json_data=[{"filename": "a.py", "status": "modified", "patch": "x"}])
        if url.endswith("/pulls/1"):
            return _pr_info()
        if url.endswith("/contents/a.py"):
            return _FakeResponse(404)
        raise AssertionError(f"unexpected url {url}")

    calls = []
    with _patch_client(responder, calls):
        result = asyncio.run(fetch_pr_data("https://github.com/octocat/Hello-World", 1))

    py_file = result["files"][0]
    assert py_file["base_content"] is None
    assert py_file["head_content"] is None


def test_content_fetch_is_capped_for_huge_prs():
    filenames = [f"file{i}.py" for i in range(MAX_FILES_FOR_CONTENT_FETCH + 5)]

    def responder(url, headers, params):
        if url.endswith("/pulls/1/files"):
            return _FakeResponse(200, json_data=[
                {"filename": name, "status": "modified", "patch": "x"} for name in filenames
            ])
        if url.endswith("/pulls/1"):
            return _pr_info()
        if "/contents/" in url:
            return _FakeResponse(200, text="content")
        raise AssertionError(f"unexpected url {url}")

    calls = []
    with _patch_client(responder, calls):
        result = asyncio.run(fetch_pr_data("https://github.com/octocat/Hello-World", 1))

    fetched = [f for f in result["files"] if f.get("head_content") is not None]
    skipped = [f for f in result["files"] if "head_content" not in f]
    assert len(fetched) == MAX_FILES_FOR_CONTENT_FETCH
    assert len(skipped) == 5
