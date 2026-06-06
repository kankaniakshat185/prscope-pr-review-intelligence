from fastapi import APIRouter, HTTPException, Depends, Security
from sqlalchemy import String
from sqlalchemy.orm import Session
from app.models.pr import SessionLocal, PRAnalysisResult, ReviewNote, User, SavedReview, ReviewEvent
from app.schemas.pr import (
    PRAnalysisRequest, PRAnalysisResponse, ReviewNoteBase, ReviewNoteResponse, 
    PostCommentRequest, SavedReviewCreate, SavedReviewResponse, ReviewEventResponse
)
from app.services.github import fetch_pr_data, fetch_architecture_rules
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
from app.services.reviewability_engine import calculate_reviewability
from app.services.auth import create_access_token, verify_token
from app.core.config import settings
from datetime import datetime
import json
import httpx

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
    if not settings.GITHUB_CLIENT_ID:
        return {"url": "http://localhost:8000/api/analysis/auth/github/callback?code=mock"}
    
    redirect_uri = f"https://github.com/login/oauth/authorize?client_id={settings.GITHUB_CLIENT_ID}&scope=read:user user:email"
    return {"url": redirect_uri}

@router.get("/auth/github/callback")
async def github_callback(code: str, db: Session = Depends(get_db)):
    if code == "mock":
        github_id = "123456"
        username = "dev_reviewer"
        avatar_url = "https://github.com/ghost.png"
    else:
        # Real OAuth Flow
        async with httpx.AsyncClient() as client:
            # 1. Exchange code for access token
            client_id_val = settings.GITHUB_CLIENT_ID.strip() if settings.GITHUB_CLIENT_ID else ""
            client_secret_val = settings.GITHUB_CLIENT_SECRET.strip() if settings.GITHUB_CLIENT_SECRET else ""
            
            token_res = await client.post(
                "https://github.com/login/oauth/access_token",
                data={
                    "client_id": client_id_val,
                    "client_secret": client_secret_val,
                    "code": code
                },
                headers={"Accept": "application/json"}
            )
            token_data = token_res.json()
            access_token = token_data.get("access_token")
            
            if not access_token:
                raise HTTPException(status_code=400, detail=f"Failed to get access token from GitHub: {token_data}. Secret len: {len(client_secret_val)}, ID len: {len(client_id_val)}")
                
            # 2. Fetch user profile
            user_res = await client.get(
                "https://api.github.com/user",
                headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"}
            )
            user_data = user_res.json()
            github_id = str(user_data.get("id"))
            username = user_data.get("login")
            avatar_url = user_data.get("avatar_url")

    # 3. Create or update user
    user = db.query(User).filter(User.github_id == github_id).first()
    if not user:
        user = User(
            github_id=github_id,
            username=username,
            avatar_url=avatar_url,
            email=username + "@github.com"
        )
        db.add(user)
    else:
        user.username = username
        user.avatar_url = avatar_url
    
    db.commit()
    db.refresh(user)

    # 4. Generate our backend JWT
    token = create_access_token(data={"sub": str(user.id)})
    user_payload = {"username": user.username, "avatar_url": user.avatar_url}
    
    if code == "mock":
        return {"access_token": token, "token_type": "bearer", "user": user_payload}
        
    # 5. Return HTML to postMessage back to the extension
    html_content = f"""
    <html>
        <body>
            <script>
                window.opener.postMessage({{
                    "access_token": "{token}",
                    "user": {json.dumps(user_payload)}
                }}, "*");
                window.close();
            </script>
            <p>Authentication successful! You can close this window.</p>
        </body>
    </html>
    """
    from fastapi.responses import HTMLResponse
    return HTMLResponse(content=html_content)


# ==================================================
# ANALYSIS ENGINE
# ==================================================

@router.post("/analyze", response_model=PRAnalysisResponse)
async def analyze_pr(request: PRAnalysisRequest):
    from app.services.context_builder import classify_pr
    
    try:
        pr_data = await fetch_pr_data(request.repo_url, request.pr_number)
        
        pr_type = classify_pr(pr_data.get('files', []))
        
        # 2. Extract changed symbols
        symbols = analyze_symbols(pr_data)

        # 3. Dependency Intelligence (Call Graph & Impact)
        dependency_graph = build_dependency_graph(pr_data.get('files', []), symbols)
        
        # Filter dependency graph (Hide symbols where upstream_callers == 0 AND downstream_calls == 0)
        filtered_functions = []
        for func in dependency_graph.get('modified_functions', []):
            up = len(func.get('called_by', []))
            down = len(func.get('calls', []))
            if up > 0 or down > 0:
                filtered_functions.append(func)
                
        # Sort by total impact descending
        filtered_functions.sort(key=lambda x: len(x.get('called_by', [])) + len(x.get('calls', [])), reverse=True)
        # Limit top 10
        dependency_graph['modified_functions'] = filtered_functions[:10]
        
        impact = analyze_impact(pr_data)
        impact["dependency_graph"] = dependency_graph
        
        # 4. Security Findings Engine
        security_findings = []
        is_docs_pr = (pr_type == "DOCS")
            
        if not is_docs_pr:
            raw_findings = analyze_security(pr_data.get('files', []))
            # Enrich with Gemini Explanations
            for finding in raw_findings:
                enriched = explain_security_finding(finding, request.gemini_api_key)
                security_findings.append(enriched)
                
        # 5. Architecture & Similarity
        rules_yaml = request.custom_rules_yaml
        if not rules_yaml:
            rules_yaml = await fetch_architecture_rules(pr_data.get("owner", ""), pr_data.get("repo", ""))
        arch_violations = validate_architecture(pr_data, rules_yaml)
        similar_incidents = find_similar_incidents(pr_data)
        
        # 6. Deterministic risk engine
        risk_score = calculate_risk(
            pr_data=pr_data,
            pr_type=pr_type,
            changed_symbols=symbols,
            dependency_impact=impact,
            security_findings=security_findings,
            architecture_violations=arch_violations
        )
        
        # 7. Deterministic reviewability engine
        reviewability = calculate_reviewability(
            pr_data=pr_data,
            security_findings=security_findings,
            architecture_violations=arch_violations
        )
        
        # 8. Build Context for LLM
        pr_context = build_pr_context(pr_data, risk_score, impact, arch_violations)
        
        # 9. LLM Generators
        checklist = generate_review_checklist(pr_context, request.gemini_api_key)
        comments = generate_review_comments(pr_context, request.gemini_api_key)
        exec_summary = generate_executive_summary(pr_context, request.gemini_api_key)
        jira_context = extract_jira_context(pr_data, request.gemini_api_key)

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
            security_findings=security_findings,
            pr_type=pr_context.get('pr_type'),
            reviewability=reviewability
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

# ==================================================
# WEBHOOKS
# ==================================================
from fastapi import Request

@router.post("/webhook/github")
async def github_webhook(request: Request):
    try:
        payload = await request.json()
    except Exception:
        return {"status": "error", "message": "Invalid JSON"}

    if "pull_request" in payload:
        action = payload.get("action")
        if action in ["opened", "synchronize", "reopened"]:
            pr_number = payload["pull_request"]["number"]
            owner = payload["repository"]["owner"]["login"]
            repo = payload["repository"]["name"]
            
            # Fire and forget analysis
            # In a real app we'd dispatch to a task queue like Celery here
            print(f"Received webhook for {owner}/{repo} PR #{pr_number}")
            
    return {"status": "received"}
