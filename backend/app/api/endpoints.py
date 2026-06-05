from fastapi import APIRouter, HTTPException, Depends, Security
from sqlalchemy import String
from sqlalchemy.orm import Session
from app.models.pr import SessionLocal, PRAnalysisResult, ReviewNote, User, SavedReview, ReviewEvent
from app.schemas.pr import (
    PRAnalysisRequest, PRAnalysisResponse, ReviewNoteBase, ReviewNoteResponse, 
    PostCommentRequest, SavedReviewCreate, SavedReviewResponse, ReviewEventResponse
)
from app.services.github import fetch_pr_data
from app.services.risk_engine import calculate_risk
from app.services.context_builder import build_pr_context
from app.services.llm import generate_review_checklist, generate_review_comments, generate_executive_summary, extract_jira_context, explain_security_finding
from app.services.symbols_analysis import analyze_symbols
from app.services.github_comments import post_review_comment
from app.services.impact_analysis import analyze_impact
from app.services.architecture import validate_architecture
from app.services.incident_similarity import find_similar_incidents
from app.services.security_engine import analyze_security
from app.services.dependency_engine import build_dependency_graph
from app.services.auth import create_access_token, verify_token
from datetime import datetime
import json

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ==================================================
# AUTHENTICATION
# ==================================================

@router.get("/auth/github/login")
def github_login():
    # In a real scenario, this redirects to https://github.com/login/oauth/authorize
    # For this implementation, we redirect to callback with a mock code
    return {"url": "http://localhost:8000/api/analysis/auth/github/callback?code=mock_github_code"}

@router.get("/auth/github/callback")
def github_callback(code: str, db: Session = Depends(get_db)):
    # Exchange code for token and fetch user info.
    # Mock user creation for workspace persistence.
    github_id = "123456"
    user = db.query(User).filter(User.github_id == github_id).first()
    if not user:
        user = User(
            github_id=github_id,
            username="dev_reviewer",
            avatar_url="https://github.com/ghost.png",
            email="dev@example.com"
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    token = create_access_token(data={"sub": str(user.id)})
    return {"access_token": token, "token_type": "bearer", "user": {"username": user.username, "avatar_url": user.avatar_url}}


# ==================================================
# ANALYSIS ENGINE
# ==================================================

@router.post("/analyze", response_model=PRAnalysisResponse)
async def analyze_pr(request: PRAnalysisRequest):
    try:
        pr_data = await fetch_pr_data(request.repo_url, request.pr_number)
        
        # 1. Deterministic risk engine
        risk_score = calculate_risk(pr_data)
        
        # 2. Extract changed symbols
        symbols = analyze_symbols(pr_data)

        # 3. Dependency Intelligence (Call Graph & Impact)
        dependency_graph = build_dependency_graph(pr_data.get('changed_files', []), symbols)
        impact = analyze_impact(pr_data)
        
        # Merge dependency graph into impact for richer UI
        impact["dependency_graph"] = dependency_graph
        
        # 4. Security Findings Engine
        security_findings = []
        is_docs_pr = False
        if pr_data.get("title", "").lower().startswith("docs:") or pr_data.get("title", "").lower().startswith("[docs]"):
            is_docs_pr = True
            
        if not is_docs_pr:
            raw_findings = analyze_security(pr_data.get('changed_files', []))
            # Enrich with Gemini Explanations
            for finding in raw_findings:
                enriched = explain_security_finding(finding)
                security_findings.append(enriched)
                
        # 5. Architecture & Similarity
        arch_violations = validate_architecture(pr_data)
        similar_incidents = find_similar_incidents(pr_data)
        
        # 6. Build Context for LLM
        pr_context = build_pr_context(pr_data, risk_score, impact, arch_violations)
        
        # 7. LLM Generators
        checklist = generate_review_checklist(pr_context)
        comments = generate_review_comments(pr_context)
        exec_summary = generate_executive_summary(pr_context)
        jira_context = extract_jira_context(pr_data)

        return PRAnalysisResponse(
            risk_score=risk_score,
            impact_analysis=impact,
            architecture_violations=arch_violations,
            similar_incidents=similar_incidents,
            review_checklist=checklist,
            suggested_comments=comments,
            jira_context=jira_context,
            executive_summary=exec_summary,
            changed_symbols=symbols,
            security_findings=security_findings
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==================================================
# SAVED REVIEWS WORKSPACE
# ==================================================

@router.post("/workspace/reviews", response_model=SavedReviewResponse)
def save_review(review: SavedReviewCreate, user_id: int = Depends(verify_token), db: Session = Depends(get_db)):
    existing = db.query(SavedReview).filter(
        SavedReview.user_id == user_id,
        SavedReview.repository == review.repository,
        SavedReview.pr_number == review.pr_number
    ).first()

    event_desc = ""
    if existing:
        event_desc = f"Status updated: {existing.review_status} -> {review.review_status}. Notes updated."
        existing.risk_score = review.risk_score
        existing.risk_category = review.risk_category
        existing.executive_summary = review.executive_summary
        existing.review_status = review.review_status
        existing.review_notes = review.review_notes
        existing.last_reviewed_at = datetime.utcnow()
        db.commit()
        db.refresh(existing)
        saved_review = existing
    else:
        event_desc = "Review Created"
        new_review = SavedReview(
            user_id=user_id,
            **review.dict(),
            last_reviewed_at=datetime.utcnow()
        )
        db.add(new_review)
        db.commit()
        db.refresh(new_review)
        saved_review = new_review

    # Log Timeline Event
    event = ReviewEvent(
        review_id=saved_review.id,
        event_type="UPDATE" if existing else "CREATE",
        description=event_desc
    )
    db.add(event)
    db.commit()

    return saved_review

@router.get("/workspace/reviews")
def get_saved_reviews(
    user_id: int = Depends(verify_token), 
    db: Session = Depends(get_db),
    status: str = None,
    sort: str = "newest", # newest, oldest, highest_risk, lowest_risk
    search: str = None
):
    query = db.query(SavedReview).filter(SavedReview.user_id == user_id)

    if status and status != "All":
        query = query.filter(SavedReview.review_status == status)

    if search:
        search_term = f"%{search}%"
        query = query.filter(
            (SavedReview.repository.ilike(search_term)) |
            (SavedReview.pr_title.ilike(search_term)) |
            (SavedReview.pr_number.cast(String).ilike(search_term))
        )

    if sort == "newest":
        query = query.order_by(SavedReview.last_reviewed_at.desc())
    elif sort == "oldest":
        query = query.order_by(SavedReview.last_reviewed_at.asc())
    elif sort == "highest_risk":
        query = query.order_by(SavedReview.risk_score.desc())
    elif sort == "lowest_risk":
        query = query.order_by(SavedReview.risk_score.asc())

    reviews = query.all()
    return reviews

@router.get("/workspace/reviews/{review_id}", response_model=SavedReviewResponse)
def get_review_detail(review_id: int, user_id: int = Depends(verify_token), db: Session = Depends(get_db)):
    review = db.query(SavedReview).filter(SavedReview.id == review_id, SavedReview.user_id == user_id).first()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    return review

@router.get("/workspace/reviews/{review_id}/events", response_model=list[ReviewEventResponse])
def get_review_events(review_id: int, user_id: int = Depends(verify_token), db: Session = Depends(get_db)):
    review = db.query(SavedReview).filter(SavedReview.id == review_id, SavedReview.user_id == user_id).first()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    
    events = db.query(ReviewEvent).filter(ReviewEvent.review_id == review_id).order_by(ReviewEvent.timestamp.desc()).all()
    return events


# ==================================================
# LEGACY ROUTES
# ==================================================

@router.post("/note", response_model=ReviewNoteResponse)
def save_review_note(note: ReviewNoteBase, db: Session = Depends(get_db)):
    existing = db.query(ReviewNote).filter(
        ReviewNote.repo_url == note.repo_url,
        ReviewNote.pr_number == note.pr_number
    ).first()

    if existing:
        existing.status = note.status
        existing.notes = note.notes
        db.commit()
        db.refresh(existing)
        return existing

    new_note = ReviewNote(**note.dict())
    db.add(new_note)
    db.commit()
    db.refresh(new_note)
    return new_note

@router.get("/note", response_model=ReviewNoteResponse)
def get_review_note(repo_url: str, pr_number: int, db: Session = Depends(get_db)):
    existing = db.query(ReviewNote).filter(
        ReviewNote.repo_url == repo_url,
        ReviewNote.pr_number == pr_number
    ).first()
    if existing:
        return existing
    raise HTTPException(status_code=404, detail="Note not found")

@router.post("/post-comment")
async def post_comment(req: PostCommentRequest):
    try:
        res = await post_review_comment(req.repo_url, req.pr_number, req.comment_body)
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/history")
def get_history(repo_url: str, db: Session = Depends(get_db)):
    results = db.query(PRAnalysisResult).filter(PRAnalysisResult.repo_url == repo_url).order_by(PRAnalysisResult.created_at.desc()).all()
    return results
