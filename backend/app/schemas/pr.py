from pydantic import BaseModel
from typing import List, Optional, Dict, Any

class PRAnalysisRequest(BaseModel):
    repo_url: str
    pr_number: int

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
