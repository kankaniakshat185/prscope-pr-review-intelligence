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

class PRAnalysisResponse(BaseModel):
    risk_score: Dict[str, Any]
    impact_analysis: Dict[str, Any]
    architecture_violations: List[Dict[str, Any]]
    similar_incidents: List[Dict[str, Any]]
    review_checklist: List[str]
    suggested_comments: List[Dict[str, Any]]
    jira_context: Optional[Dict[str, Any]]
    executive_summary: str
    changed_symbols: Dict[str, List[str]]
    security_findings: List[Dict[str, Any]] = []
    pr_type: Optional[str] = None
    reviewability: Optional[Dict[str, Any]] = None

class ReviewNoteBase(BaseModel):
    repo_url: str
    pr_number: int
    status: str
    notes: str

class ReviewNoteResponse(ReviewNoteBase):
    id: int
    created_at: Any
    updated_at: Any

    class Config:
        orm_mode = True

class PostCommentRequest(BaseModel):
    repo_url: str
    pr_number: int
    comment_body: str
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
