import ast
import asyncio
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple

import httpx
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.pr import IndexedCall, IndexedFunction, RepoIndex
from app.services.dependency_engine import CallGraphVisitor
from app.services.github import (
    _json_headers,
    fetch_compare,
    fetch_default_branch_head_sha,
    fetch_file_content,
    fetch_repo_tree,
)
from app.services.treesitter_engine import collect_calls as ts_collect_calls
from app.services.treesitter_engine import collect_definitions as ts_collect_definitions
from app.services.treesitter_engine import is_supported_file as is_treesitter_supported

# Caps how many files a single full index build will parse, bounding the
# Contents API call volume (and build time) on very large repositories -
# same "accepted, documented limitation" spirit as MAX_FILES_FOR_CONTENT_FETCH
# in github.py. Incremental updates aren't capped - they only touch files
# that actually changed since the last indexed commit.
MAX_FILES_PER_INDEX = 500

# How many file fetches run concurrently during a build. GitHub's API
# tolerates bursts, but hundreds of fully-parallel requests risk secondary
# rate limiting; this keeps the build reasonably fast without hammering it.
_FETCH_CONCURRENCY = 10


def _is_indexable(filename: str) -> bool:
    return filename.endswith(".py") or is_treesitter_supported(filename)


def _python_functions_and_calls(source: str) -> Optional[Tuple[Set[str], List[Tuple[str, str]]]]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    names = {
        node.name for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }
    visitor = CallGraphVisitor()
    visitor.visit(tree)
    return names, visitor.calls


def _treesitter_functions_and_calls(source: str, filename: str) -> Optional[Tuple[Set[str], List[Tuple[str, str]]]]:
    defs = ts_collect_definitions(source, filename)
    if defs is None:
        return None
    functions, _classes = defs
    calls = ts_collect_calls(source, filename) or []
    return set(functions.keys()), calls


def _extract(filename: str, source: str) -> Optional[Tuple[Set[str], List[Tuple[str, str]]]]:
    if filename.endswith(".py"):
        return _python_functions_and_calls(source)
    if is_treesitter_supported(filename):
        return _treesitter_functions_and_calls(source, filename)
    return None


def _replace_file_entries(db: Session, repo_index_id: int, file_path: str, extracted: Optional[Tuple[Set[str], List[Tuple[str, str]]]]) -> None:
    db.query(IndexedFunction).filter(
        IndexedFunction.repo_index_id == repo_index_id, IndexedFunction.file_path == file_path
    ).delete()
    db.query(IndexedCall).filter(
        IndexedCall.repo_index_id == repo_index_id, IndexedCall.caller_file_path == file_path
    ).delete()

    if extracted is None:
        return
    names, calls = extracted
    for name in names:
        db.add(IndexedFunction(repo_index_id=repo_index_id, file_path=file_path, name=name))
    for caller, callee in calls:
        db.add(IndexedCall(repo_index_id=repo_index_id, caller_file_path=file_path, caller_name=caller, callee_name=callee))


async def _fetch_many(owner: str, repo: str, paths: List[str], ref: str) -> Dict[str, Optional[str]]:
    headers = _json_headers()
    results: Dict[str, Optional[str]] = {}
    semaphore = asyncio.Semaphore(_FETCH_CONCURRENCY)

    async with httpx.AsyncClient() as client:
        async def _one(path: str) -> None:
            async with semaphore:
                results[path] = await fetch_file_content(client, headers, owner, repo, path, ref)

        await asyncio.gather(*(_one(p) for p in paths))

    return results


def _recount(db: Session, repo_index: RepoIndex) -> None:
    repo_index.function_count = (
        db.query(IndexedFunction).filter(IndexedFunction.repo_index_id == repo_index.id).count()
    )
    repo_index.file_count = (
        db.query(IndexedFunction.file_path)
        .filter(IndexedFunction.repo_index_id == repo_index.id)
        .distinct()
        .count()
    )


async def build_or_update_index(db: Session, owner: str, repo: str) -> RepoIndex:
    """
    Builds (or incrementally refreshes) the persisted, repo-wide function/
    call index for one repository. First call for a repo does a full scan
    of its default branch (bounded by MAX_FILES_PER_INDEX); subsequent
    calls diff the current default-branch head against the last indexed
    commit (GitHub's compare API) and only re-parse files that actually
    changed - additions/deletions/modifications all handled by deleting
    that file's prior rows and, for anything but a removal, re-inserting
    freshly parsed ones.
    """
    repository = f"{owner}/{repo}"
    repo_index = db.query(RepoIndex).filter(RepoIndex.repository == repository).first()

    _branch, head_sha = await fetch_default_branch_head_sha(owner, repo)

    if repo_index is not None and repo_index.status == "ready" and repo_index.indexed_sha == head_sha:
        return repo_index  # already reflects the current default-branch head

    if repo_index is None:
        repo_index = RepoIndex(repository=repository, status="indexing")
        db.add(repo_index)
        db.commit()
        db.refresh(repo_index)
    else:
        repo_index.status = "indexing"
        db.commit()

    try:
        if repo_index.indexed_sha:
            changed_files = await fetch_compare(owner, repo, repo_index.indexed_sha, head_sha)
            for f in changed_files:
                path = f.get("filename", "")
                if f.get("status") == "removed":
                    _replace_file_entries(db, repo_index.id, path, None)
                    continue
                if not _is_indexable(path):
                    continue
                contents = await _fetch_many(owner, repo, [path], head_sha)
                content = contents.get(path)
                extracted = _extract(path, content) if content is not None else None
                _replace_file_entries(db, repo_index.id, path, extracted)
        else:
            tree_entries = await fetch_repo_tree(owner, repo, head_sha)
            indexable_paths = [
                e["path"] for e in tree_entries
                if e.get("type") == "blob" and _is_indexable(e.get("path", ""))
            ][:MAX_FILES_PER_INDEX]

            contents = await _fetch_many(owner, repo, indexable_paths, head_sha)
            for path in indexable_paths:
                content = contents.get(path)
                extracted = _extract(path, content) if content is not None else None
                _replace_file_entries(db, repo_index.id, path, extracted)

        db.commit()

        _recount(db, repo_index)
        repo_index.status = "ready"
        repo_index.indexed_sha = head_sha
        repo_index.indexed_at = datetime.utcnow()
        repo_index.error_message = None
        db.commit()

    except Exception as e:
        db.rollback()
        repo_index.status = "failed"
        repo_index.error_message = str(e)[:500]
        db.commit()
        raise

    return repo_index


def enrich_with_repo_wide_blast_radius(db: Session, owner: str, repo: str, dependency_graph: Dict[str, Any]) -> None:
    """
    Read-only: attaches repo_index_status/repo_index_updated_at to the
    dependency graph, and - if a ready index exists - a repo_wide_called_by
    list per modified/added function, sourced from callers anywhere in the
    repo rather than just the files this PR touched. Never builds or
    updates the index itself (that's an explicit, separate action) - a repo
    with no index yet just gets "not_indexed" and no enrichment, same
    output as before this feature existed.
    """
    repository = f"{owner}/{repo}"
    repo_index = db.query(RepoIndex).filter(RepoIndex.repository == repository).first()

    dependency_graph["repo_index_status"] = repo_index.status if repo_index else "not_indexed"
    dependency_graph["repo_index_updated_at"] = (
        repo_index.indexed_at.isoformat() if repo_index and repo_index.indexed_at else None
    )

    if repo_index is None or repo_index.status != "ready":
        return

    for func_entry in dependency_graph.get("modified_functions", []):
        name = func_entry.get("function")
        known_callers = set(func_entry.get("called_by", []))

        rows = (
            db.query(IndexedCall.caller_file_path, IndexedCall.caller_name)
            .filter(IndexedCall.repo_index_id == repo_index.id, IndexedCall.callee_name == name)
            .distinct()
            .all()
        )
        repo_wide = sorted({
            f"{file_path}:{caller_name}" for file_path, caller_name in rows
            if caller_name not in known_callers
        })
        if repo_wide:
            func_entry["repo_wide_called_by"] = repo_wide
