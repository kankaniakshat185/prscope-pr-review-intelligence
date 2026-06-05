import httpx
from typing import Dict, Any
from app.core.config import settings

async def fetch_pr_data(repo_url: str, pr_number: int) -> Dict[str, Any]:
    # Parse repo url like https://github.com/owner/repo
    parts = repo_url.rstrip('/').split('/')
    if len(parts) < 2:
        raise ValueError("Invalid GitHub repository URL")
    owner, repo = parts[-2], parts[-1]
    
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "User-Agent": "PR-Copilot"
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
        "files": files_info
    }
