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
