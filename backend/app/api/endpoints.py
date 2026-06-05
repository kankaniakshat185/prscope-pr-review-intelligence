from fastapi import APIRouter, HTTPException
from app.schemas.pr import PRAnalysisRequest, PRAnalysisResponse
from app.services.github import fetch_pr_data
from app.services.risk_engine import calculate_risk
from app.services.context_builder import build_pr_context
from app.services.llm import generate_review_checklist, generate_review_comments, generate_executive_summary, extract_jira_context
from app.services.symbols_analysis import analyze_symbols
from app.services.github_comments import post_review_comment
from app.models.pr import SessionLocal, PRAnalysisResult, ReviewNote
from app.schemas.pr import PRAnalysisRequest, PRAnalysisResponse, ReviewNoteBase, ReviewNoteResponse, PostCommentRequest
from sqlalchemy.orm import Session
from fastapi import APIRouter, HTTPException, Depends
from app.services.impact_analysis import analyze_impact
from app.services.architecture import validate_architecture
from app.services.incident_similarity import find_similar_incidents

router = APIRouter()

@router.post("/analyze", response_model=PRAnalysisResponse)
async def analyze_pr(request: PRAnalysisRequest):
    try:
        # Fetch PR data from GitHub
        pr_data = await fetch_pr_data(request.repo_url, request.pr_number)
        
        # Run deterministic risk engine
        risk_score = calculate_risk(pr_data)
        
        # Analyze dependency impact
        impact = analyze_impact(pr_data)
        
        # Validate architecture rules
        arch_violations = validate_architecture(pr_data)
        
        # Incident similarity via ChromaDB
        similar_incidents = find_similar_incidents(pr_data)
        
        # Build deterministic context for AI
        pr_context = build_pr_context(pr_data, risk_score, impact, arch_violations)
        
        # LLM-based features using context
        checklist = generate_review_checklist(pr_context)
        comments = generate_review_comments(pr_context)
        exec_summary = generate_executive_summary(pr_context)
        jira_context = extract_jira_context(pr_data)

        # Save to database
        db = SessionLocal()
        try:
            db_result = PRAnalysisResult(
                repo_url=request.repo_url,
                pr_number=request.pr_number,
                risk_score=risk_score["score"],
                risk_category=risk_score["category"],
                executive_summary=exec_summary
            )
            db.add(db_result)
            db.commit()
        except Exception as e:
            print(f"Warning: Failed to save to DB {e}")
        finally:
            db.close()

        # Changed Symbols
        symbols = analyze_symbols(pr_data)

        return PRAnalysisResponse(
            risk_score=risk_score,
            impact_analysis=impact,
            architecture_violations=arch_violations,
            similar_incidents=similar_incidents,
            review_checklist=checklist,
            suggested_comments=comments,
            jira_context=jira_context,
            executive_summary=exec_summary,
            changed_symbols=symbols
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

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

    new_note = ReviewNote(
        repo_url=note.repo_url,
        pr_number=note.pr_number,
        status=note.status,
        notes=note.notes
    )
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
