import httpx
from typing import Dict, Any
from app.core.config import settings

async def post_review_comment(repo_url: str, pr_number: int, comment_body: str, github_token: str = None) -> Dict[str, Any]:
    active_token = github_token or settings.GITHUB_TOKEN
    if not active_token:
        raise ValueError("GitHub token is required to post comments. Please provide one in the extension settings or backend env.")

    parts = repo_url.rstrip('/').split('/')
    if len(parts) < 2:
        raise ValueError("Invalid GitHub repository URL")
    owner, repo = parts[-2], parts[-1]
    
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "Authorization": f"Bearer {active_token}",
        "User-Agent": "PRScope"
    }

    # Post to issue comments API (PRs are issues in GitHub API for general comments)
    api_url = f"https://api.github.com/repos/{owner}/{repo}/issues/{pr_number}/comments"
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            api_url,
            headers=headers,
            json={"body": comment_body}
        )
        response.raise_for_status()
        data = response.json()
        
        return {
            "comment_id": "internal_" + str(data.get("id")),
            "github_comment_id": data.get("id"),
            "posted_at": data.get("created_at")
        }
