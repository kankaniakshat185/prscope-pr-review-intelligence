import asyncio
import httpx
from typing import Dict, Any, Optional
from app.core.config import settings
from app.services.treesitter_engine import is_supported_file as is_treesitter_supported

# How many changed files (of a language we can actually parse - Python or a
# tree-sitter-supported one) get real base/head content fetched via the
# Contents API per analysis. Bounds the extra API call volume (2 calls/file)
# on huge PRs; files beyond the cap fall back to diff-fragment reconstruction
# in symbols_analysis.py / dependency_engine.py, same as before this existed.
MAX_FILES_FOR_CONTENT_FETCH = 30


def _is_parseable_file(filename: str) -> bool:
    return filename.endswith(".py") or is_treesitter_supported(filename)


async def fetch_file_content(
    client: httpx.AsyncClient, headers: Dict[str, str], owner: str, repo: str, path: str, ref: Optional[str]
) -> Optional[str]:
    """
    Raw file content at a specific commit via the Contents API. Returns None
    (not raises) whenever we can't get real content back - no ref (e.g. file
    doesn't exist on that side of the diff), the path not existing at that
    ref, a transient network failure, etc. - so callers can uniformly treat
    "None" as "fall back to the diff-fragment approach" instead of handling
    several distinct failure modes.
    """
    if not ref:
        return None
    raw_headers = {**headers, "Accept": "application/vnd.github.v3.raw"}
    try:
        response = await client.get(
            f"https://api.github.com/repos/{owner}/{repo}/contents/{path}",
            headers=raw_headers,
            params={"ref": ref},
        )
    except httpx.HTTPError:
        return None
    if response.status_code != 200:
        return None
    return response.text


async def fetch_pr_data(repo_url: str, pr_number: int) -> Dict[str, Any]:
    # Parse repo url like https://github.com/owner/repo
    parts = repo_url.rstrip('/').split('/')
    if len(parts) < 2:
        raise ValueError("Invalid GitHub repository URL")
    owner, repo = parts[-2], parts[-1]

    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "PRScope"
    }
    if settings.GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {settings.GITHUB_TOKEN}"

    api_base = f"https://api.github.com/repos/{owner}/{repo}"

    async with httpx.AsyncClient() as client:
        # Fetch PR details
        pr_response = await client.get(f"{api_base}/pulls/{pr_number}", headers=headers)
        pr_response.raise_for_status()
        pr_info = pr_response.json()

        # Fetch files changed
        files_response = await client.get(f"{api_base}/pulls/{pr_number}/files", headers=headers)
        files_response.raise_for_status()
        files_info = files_response.json()

        base_sha = pr_info.get("base", {}).get("sha")
        head_sha = pr_info.get("head", {}).get("sha")

        # Fetch real base/head file content for Python and JS/TS files -
        # this is what symbol extraction and the dependency graph now
        # analyze, instead of reconstructing a "fake" source from diff-hunk
        # text alone.
        parseable_files = [f for f in files_info if _is_parseable_file(f.get("filename", ""))][:MAX_FILES_FOR_CONTENT_FETCH]

        async def _attach_content(f: Dict[str, Any]) -> None:
            status = f.get("status")
            # Renamed files live under a different path on the base side.
            base_path = f.get("previous_filename") or f.get("filename", "")
            head_path = f.get("filename", "")
            base_content, head_content = await asyncio.gather(
                fetch_file_content(client, headers, owner, repo, base_path, base_sha if status != "added" else None),
                fetch_file_content(client, headers, owner, repo, head_path, head_sha if status != "removed" else None),
            )
            f["base_content"] = base_content
            f["head_content"] = head_content

        await asyncio.gather(*(_attach_content(f) for f in parseable_files))

    # Extract metadata
    return {
        "owner": owner,
        "repo": repo,
        "number": pr_number,
        "title": pr_info.get("title", ""),
        "description": pr_info.get("body", "") or "",
        "additions": pr_info.get("additions", 0),
        "deletions": pr_info.get("deletions", 0),
        "changed_files": pr_info.get("changed_files", 0),
        "files": files_info,
        "head_sha": head_sha,
        "base_sha": base_sha,
    }

async def fetch_pr_head_sha(repo_url: str, pr_number: int) -> str:
    """
    Just the head commit SHA - used by the commit-status endpoint, which
    doesn't need the full diff/files payload fetch_pr_data returns.
    """
    parts = repo_url.rstrip('/').split('/')
    if len(parts) < 2:
        raise ValueError("Invalid GitHub repository URL")
    owner, repo = parts[-2], parts[-1]

    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "PRScope"
    }
    if settings.GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {settings.GITHUB_TOKEN}"

    async with httpx.AsyncClient() as client:
        response = await client.get(f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}", headers=headers)
        response.raise_for_status()
        return response.json()["head"]["sha"]


async def fetch_architecture_rules(owner: str, repo: str) -> str:
    headers = {
        "Accept": "application/vnd.github.v3.raw",
        "User-Agent": "PRScope"
    }
    if settings.GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {settings.GITHUB_TOKEN}"

    url = f"https://api.github.com/repos/{owner}/{repo}/contents/.prscope.yml"
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)
        if response.status_code == 200:
            return response.text
        return None
