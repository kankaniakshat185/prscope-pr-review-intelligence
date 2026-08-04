import httpx
from typing import Dict, Any, Optional
from app.core.config import settings

VALID_STATES = {"error", "failure", "pending", "success"}

# GitHub truncates/rejects descriptions beyond this length.
MAX_DESCRIPTION_LENGTH = 140


async def post_commit_status(
    repo_url: str,
    sha: str,
    state: str,
    description: str,
    context: str = "prscope/risk-review",
    target_url: Optional[str] = None,
    github_token: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Posts a commit status via GitHub's Statuses API, so a risk verdict shows
    up directly in the PR's own "Checks" section rather than only inside the
    extension. Deliberately the Statuses API and not the newer Checks API -
    Checks requires a GitHub App identity (installation tokens, app
    manifest); Statuses works with the same personal access token already
    used for posting comments, at the cost of a plainer single-line status
    instead of rich inline annotations.
    """
    active_token = github_token or settings.GITHUB_TOKEN
    if not active_token:
        raise ValueError("GitHub token is required to publish a status. Please provide one in the extension settings or backend env.")

    if state not in VALID_STATES:
        raise ValueError(f"Invalid status state '{state}' - must be one of {sorted(VALID_STATES)}")

    parts = repo_url.rstrip('/').split('/')
    if len(parts) < 2:
        raise ValueError("Invalid GitHub repository URL")
    owner, repo = parts[-2], parts[-1]

    headers = {
        "Accept": "application/vnd.github.v3+json",
        "Authorization": f"Bearer {active_token}",
        "User-Agent": "PRScope"
    }

    payload: Dict[str, Any] = {
        "state": state,
        "description": description[:MAX_DESCRIPTION_LENGTH],
        "context": context,
    }
    if target_url:
        payload["target_url"] = target_url

    api_url = f"https://api.github.com/repos/{owner}/{repo}/statuses/{sha}"

    async with httpx.AsyncClient() as client:
        response = await client.post(api_url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()

        return {
            "status_id": data.get("id"),
            "state": data.get("state"),
            "created_at": data.get("created_at"),
        }
