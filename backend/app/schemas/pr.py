from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from datetime import datetime

class PRAnalysisRequest(BaseModel):
    repo_url: str
    pr_number: int
    gemini_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    ai_provider: str = "gemini"
    custom_rules_yaml: Optional[str] = None

class PRDeterministicResponse(BaseModel):
    """
    Everything that doesn't require an LLM call: fast (typically well under
    a second), returned first so the UI has something to render immediately
    instead of blocking on the slower AI-generated content below.
    """
    risk_score: Dict[str, Any]
    impact_analysis: Dict[str, Any]
    architecture_violations: List[Dict[str, Any]]
    similar_incidents: List[Dict[str, Any]]
    changed_symbols: Dict[str, List[str]]
    security_findings: List[Dict[str, Any]] = []  # deterministic detection only - no ai_* fields yet
    pr_type: Optional[str] = None
    reviewability: Optional[Dict[str, Any]] = None
    pr_title: Optional[str] = None
    has_tests: bool = False


class PREnrichmentResponse(BaseModel):
    """
    The LLM-generated content: slower (can legitimately take a minute-plus
    with retry/backoff), fetched separately after PRDeterministicResponse so
    the UI can show deterministic results instantly while this streams in.
    """
    review_checklist: List[str]
    suggested_comments: List[Dict[str, Any]]
    jira_context: Optional[Dict[str, Any]]
    executive_summary: str
    security_findings: List[Dict[str, Any]] = []  # same findings as the deterministic response, now with ai_* fields populated

class PostCommentRequest(BaseModel):
    repo_url: str
    pr_number: int
    comment_body: str
    github_token: Optional[str] = None

class PostStatusRequest(BaseModel):
    repo_url: str
    pr_number: int
    state: str  # "success" | "failure" | "error" | "pending"
    description: str
    target_url: Optional[str] = None
    github_token: Optional[str] = None

class SavedReviewCreate(BaseModel):
    repository: str
    repository_owner: str
    repository_name: str
    pr_number: int
    pr_title: str
    pr_url: str
    risk_score: float
    risk_category: str
    executive_summary: str
    review_status: str
    review_notes: str

class SavedReviewResponse(SavedReviewCreate):
    id: int
    user_id: int
    created_at: datetime
    updated_at: datetime
    last_reviewed_at: Optional[datetime]

    class Config:
        orm_mode = True

class ReviewEventResponse(BaseModel):
    id: int
    review_id: int
    event_type: str
    description: str
    timestamp: datetime

    class Config:
        orm_mode = True

class UserResponse(BaseModel):
    id: int
    github_id: str
    username: str
    avatar_url: str
    email: Optional[str]
    created_at: datetime

    class Config:
        orm_mode = True
