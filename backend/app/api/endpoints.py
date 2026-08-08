from fastapi import APIRouter, HTTPException, Depends, Security, Header
from fastapi.concurrency import run_in_threadpool
from typing import Dict, Any, Optional
from sqlalchemy import String
from sqlalchemy.orm import Session
from app.models.pr import SessionLocal, User, SavedReview, ReviewEvent, RepoIndex
from app.schemas.pr import (
    PRAnalysisRequest, PRDeterministicResponse, PREnrichmentResponse,
    PostCommentRequest, PostStatusRequest, RepoIndexRequest, RepoIndexStatusResponse,
    IncidentCreate, IncidentResponse,
    SavedReviewCreate, SavedReviewResponse, ReviewEventResponse
)
from app.services.github import fetch_pr_data, fetch_architecture_rules, fetch_pr_head_sha, verify_repo_access
from app.services.github_status import post_commit_status
from app.services.risk_engine import calculate_risk
from app.services.context_builder import build_pr_context
from app.services.llm import generate_review_bundle, explain_security_findings_batch
from app.services.symbols_analysis import analyze_symbols
from app.services.github_comments import post_review_comment
from app.services.impact_analysis import analyze_impact
from app.services.architecture import validate_architecture
from app.services.incident_similarity import find_similar_incidents, add_team_incident, list_team_incidents
from app.services.security_engine import analyze_security
from app.services.dependency_engine import build_dependency_graph
from app.services.complexity_engine import compute_function_complexities
from app.services.reviewability_engine import calculate_reviewability
from app.services.auth import create_access_token, verify_token
from app.services.rate_limiter import rate_limited_user
from app.services.webhook_debouncer import WebhookDebouncer
from app.services.repo_index_engine import build_or_update_index, enrich_with_repo_wide_blast_radius
from app.core.config import settings
from datetime import datetime
import asyncio
import json
import httpx
import hashlib
import hmac

router = APIRouter()

# Gap between successive LLM calls within one analysis. A single analysis
# makes several calls back-to-back (one per security finding, plus checklist/
# comments/summary/jira); spacing them out reduces the odds of tripping a
# free-tier per-minute quota, at the cost of a slower (but reliable) analysis.
LLM_CALL_SPACING_SECONDS = 5

# security_engine.analyze_security has no cap on how many findings it can
# return; without a limit here, a messy PR could trigger dozens of AI-
# explanation calls and blow well past any reasonable analysis time budget.
MAX_AI_EXPLAINED_FINDINGS = 10

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
        if settings.ENABLE_MOCK_AUTH:
            return {"url": "http://localhost:8000/api/analysis/auth/github/callback?code=mock"}
        raise HTTPException(
            status_code=503,
            detail="GitHub OAuth is not configured (GITHUB_CLIENT_ID/GITHUB_CLIENT_SECRET). "
                   "For local development without a GitHub OAuth app, set ENABLE_MOCK_AUTH=true."
        )

    redirect_uri = f"https://github.com/login/oauth/authorize?client_id={settings.GITHUB_CLIENT_ID}&scope=read:user user:email"
    return {"url": redirect_uri}

@router.get("/auth/github/callback")
async def github_callback(code: str, db: Session = Depends(get_db)):
    if code == "mock":
        if not settings.ENABLE_MOCK_AUTH:
            raise HTTPException(status_code=403, detail="Mock authentication is disabled.")
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
                print(f"GitHub OAuth token exchange failed: {token_data}")
                raise HTTPException(status_code=400, detail="Failed to authenticate with GitHub. Please try again.")
                
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

async def _run_deterministic_pipeline(pr_data: Dict[str, Any], custom_rules_yaml: Optional[str]) -> Dict[str, Any]:
    """
    Everything that doesn't need an LLM call. Shared by both /analyze (which
    returns this directly, fast) and /analyze/enrich (which needs the same
    risk_score/impact/arch_violations/security_findings to build its LLM
    prompt context, and to run AI-explanation on top of these same
    deterministic security findings). Each endpoint calls this
    independently and re-fetches pr_data itself rather than one passing
    cached state to the other - keeps both endpoints simple and stateless,
    at the cost of some duplicated (but fast, non-LLM) computation.
    """
    from app.services.context_builder import classify_pr

    pr_type = classify_pr(pr_data.get('files', []))
    has_tests = any(
        "test" in f.get("filename", "").lower() or f.get("filename", "").startswith("tests/")
        for f in pr_data.get('files', [])
    )

    symbols = analyze_symbols(pr_data)

    # Cyclomatic complexity (Python files only - same diff-fragment
    # limitation as symbol extraction and dependency graph construction)
    complexity_data: Dict[str, int] = {}
    for changed_file in pr_data.get('files', []):
        if changed_file.get('filename', '').endswith('.py'):
            for fn_name, complexity in compute_function_complexities(changed_file.get('patch', '')).items():
                complexity_data[fn_name] = max(complexity_data.get(fn_name, 0), complexity)

    # Dependency Intelligence (Call Graph & Impact)
    dependency_graph = build_dependency_graph(pr_data.get('files', []), symbols)

    # Repo-wide blast radius, if a persisted index exists for this repo
    # (see repo_index_engine.py) - done before the filter/rank step below,
    # since a function that looks "locally unconnected" (nothing in this
    # PR's own changed files calls it) might still be heavily called from
    # elsewhere in the repo, which is exactly the case this feature exists
    # to surface. Read-only: never builds/updates the index itself.
    db = SessionLocal()
    try:
        await run_in_threadpool(
            enrich_with_repo_wide_blast_radius, db, pr_data.get("owner", ""), pr_data.get("repo", ""), dependency_graph
        )
    finally:
        db.close()

    filtered_functions = []
    for func in dependency_graph.get('modified_functions', []):
        up = len(func.get('called_by', [])) + len(func.get('repo_wide_called_by', []))
        down = len(func.get('calls', []))
        if up > 0 or down > 0:
            filtered_functions.append(func)

    filtered_functions.sort(
        key=lambda x: len(x.get('called_by', [])) + len(x.get('calls', [])) + len(x.get('repo_wide_called_by', [])),
        reverse=True
    )
    dependency_graph['modified_functions'] = filtered_functions[:10]

    impact = analyze_impact(pr_data)
    impact["dependency_graph"] = dependency_graph

    # Security Findings Engine (deterministic detection only - AI
    # explanations, if any, are added later by the enrichment endpoint)
    security_findings = []
    is_docs_pr = (pr_type == "DOCS")
    if not is_docs_pr:
        # Offloaded to a thread pool: for Python files this shells out to
        # bandit (a subprocess call), which must not block the event loop.
        security_findings = await run_in_threadpool(analyze_security, pr_data.get('files', []))

    rules_yaml = custom_rules_yaml
    if not rules_yaml:
        rules_yaml = await fetch_architecture_rules(pr_data.get("owner", ""), pr_data.get("repo", ""))
    arch_violations = validate_architecture(pr_data, rules_yaml)
    similar_incidents = find_similar_incidents(pr_data)

    risk_score = calculate_risk(
        pr_data=pr_data,
        pr_type=pr_type,
        changed_symbols=symbols,
        dependency_impact=impact,
        security_findings=security_findings,
        architecture_violations=arch_violations,
        complexity_data=complexity_data
    )

    reviewability = calculate_reviewability(
        pr_data=pr_data,
        security_findings=security_findings,
        architecture_violations=arch_violations
    )

    return {
        "pr_type": pr_type,
        "has_tests": has_tests,
        "symbols": symbols,
        "impact": impact,
        "security_findings": security_findings,
        "arch_violations": arch_violations,
        "similar_incidents": similar_incidents,
        "risk_score": risk_score,
        "reviewability": reviewability,
    }


@router.post("/analyze", response_model=PRDeterministicResponse)
async def analyze_pr(request: PRAnalysisRequest, user_id: int = Depends(rate_limited_user)):
    try:
        pr_data = await fetch_pr_data(request.repo_url, request.pr_number)
        result = await _run_deterministic_pipeline(pr_data, request.custom_rules_yaml)

        return PRDeterministicResponse(
            risk_score=result["risk_score"],
            impact_analysis=result["impact"],
            architecture_violations=result["arch_violations"],
            similar_incidents=result["similar_incidents"],
            changed_symbols=result["symbols"],
            security_findings=result["security_findings"],
            pr_type=result["pr_type"],
            reviewability=result["reviewability"],
            pr_title=pr_data.get('title', ''),
            has_tests=result["has_tests"]
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze/enrich", response_model=PREnrichmentResponse)
async def enrich_pr_analysis(request: PRAnalysisRequest, user_id: int = Depends(rate_limited_user)):
    """
    The slow, LLM-generated half of analysis: AI explanations for security
    findings, the review checklist, suggested comments, executive summary,
    and Jira context. Called separately from (and after) /analyze so the UI
    can render deterministic results immediately instead of blocking on
    this - which can legitimately take a minute or more with the retry/
    backoff logic in llm.py.

    Only ever makes at most 2 LLM calls total (one batched explanation call
    for security findings, one combined call for checklist/comments/
    summary/jira) instead of up to ~14 separate ones - see
    explain_security_findings_batch and generate_review_bundle in llm.py.
    That's the main lever against exhausting a shared free-tier key's quota.
    """
    try:
        active_key = {
            "openai": request.openai_api_key,
            "groq": request.groq_api_key,
        }.get(request.ai_provider, request.gemini_api_key)
        provider = request.ai_provider

        pr_data = await fetch_pr_data(request.repo_url, request.pr_number)
        result = await _run_deterministic_pipeline(pr_data, request.custom_rules_yaml)

        # Findings beyond MAX_AI_EXPLAINED_FINDINGS still appear with their
        # deterministic detection (name/severity/file/snippet) - they're
        # just excluded from the batch explanation call, bounding its
        # prompt/output size on PRs with many findings.
        findings_to_explain = result["security_findings"][:MAX_AI_EXPLAINED_FINDINGS]
        findings_overflow = result["security_findings"][MAX_AI_EXPLAINED_FINDINGS:]

        explained = await run_in_threadpool(explain_security_findings_batch, findings_to_explain, active_key, provider)
        security_findings = explained + findings_overflow
        if findings_to_explain:
            await asyncio.sleep(LLM_CALL_SPACING_SECONDS)

        pr_context = build_pr_context(pr_data, result["risk_score"], result["impact"], result["arch_violations"])

        # (blocking HTTP call; run_in_threadpool keeps the event loop free
        # for other requests instead of stalling the whole server)
        bundle = await run_in_threadpool(generate_review_bundle, pr_context, pr_data, active_key, provider)

        return PREnrichmentResponse(
            review_checklist=bundle["review_checklist"],
            suggested_comments=bundle["suggested_comments"],
            jira_context=bundle["jira_context"],
            executive_summary=bundle["executive_summary"],
            security_findings=security_findings,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==================================================
# REPO-WIDE INDEX (cross-file blast radius)
# ==================================================

# Repos currently being indexed - guards against one process kicking off two
# concurrent builds for the same repo (e.g. a double-click). In-memory,
# per-process, same tradeoff as rate_limiter.py/webhook_debouncer.py.
_index_builds_in_progress: set = set()


def _parse_owner_repo(repo_url: str) -> tuple:
    parts = repo_url.rstrip('/').split('/')
    if len(parts) < 2:
        raise HTTPException(status_code=400, detail="Invalid GitHub repository URL")
    return parts[-2], parts[-1]


@router.post("/index/build")
async def trigger_repo_index_build(request: RepoIndexRequest, user_id: int = Depends(verify_token)):
    """
    Kicks off a full-repo index build (or incremental refresh) in the
    background and returns immediately - a first build can take a while
    (up to MAX_FILES_PER_INDEX file fetches), so this isn't awaited inline.
    Poll GET /index/status for progress.
    """
    owner, repo = _parse_owner_repo(request.repo_url)
    repository = f"{owner}/{repo}"

    if repository in _index_builds_in_progress:
        return {"status": "already_in_progress", "repository": repository}

    _index_builds_in_progress.add(repository)

    async def _run():
        db = SessionLocal()
        try:
            await build_or_update_index(db, owner, repo)
        except Exception as e:
            print(f"Repo index build failed for {repository}: {e}")
        finally:
            db.close()
            _index_builds_in_progress.discard(repository)

    asyncio.create_task(_run())
    return {"status": "started", "repository": repository}


@router.get("/index/status", response_model=RepoIndexStatusResponse)
def get_repo_index_status(repo_url: str, user_id: int = Depends(verify_token), db: Session = Depends(get_db)):
    owner, repo = _parse_owner_repo(repo_url)
    repository = f"{owner}/{repo}"

    repo_index = db.query(RepoIndex).filter(RepoIndex.repository == repository).first()
    if repo_index is None:
        return RepoIndexStatusResponse(repository=repository, status="not_indexed")

    return RepoIndexStatusResponse(
        repository=repository,
        status=repo_index.status,
        indexed_sha=repo_index.indexed_sha,
        indexed_at=repo_index.indexed_at,
        file_count=repo_index.file_count,
        function_count=repo_index.function_count,
        error_message=repo_index.error_message,
    )

# ==================================================
# TEAM INCIDENTS
# ==================================================

@router.post("/incidents", response_model=IncidentResponse)
def report_incident(payload: IncidentCreate, user_id: int = Depends(verify_token), db: Session = Depends(get_db)):
    """
    Lets a team record a real incident from their own repository, so
    find_similar_incidents() isn't limited to the 3 hand-written stub
    examples forever - added incidents are picked up by that same search
    immediately (see incident_similarity.py).
    """
    if not payload.description.strip():
        raise HTTPException(status_code=400, detail="description is required")
    user = db.query(User).filter(User.id == user_id).first()
    return add_team_incident(
        repository=payload.repository,
        description=payload.description,
        severity=payload.severity,
        reported_by=user.username if user else None,
    )


@router.get("/incidents", response_model=list[IncidentResponse])
def get_team_incidents(repository: str, user_id: int = Depends(verify_token)):
    return list_team_incidents(repository)


# ==================================================
# SAVED REVIEWS WORKSPACE
# ==================================================

async def _has_team_access(repository: str, github_token: Optional[str]) -> bool:
    """
    Gate for team-shared review visibility: does this specific GitHub
    token's owner have real, verifiable access to this repository right
    now? Deliberately NOT "have they saved a review here before" - that
    was trivially satisfiable by any PRScope user for any repo the shared
    backend's own token could see, since /analyze never checked the
    caller's own GitHub identity against the repo at all.
    """
    if not github_token:
        return False
    if "/" not in repository:
        return False
    owner, repo = repository.split("/", 1)
    return await verify_repo_access(owner, repo, github_token)


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
async def get_saved_reviews(
    user_id: int = Depends(verify_token),
    db: Session = Depends(get_db),
    status: str = None,
    sort: str = "newest", # newest, oldest, highest_risk, lowest_risk
    search: str = None,
    repository: str = None,
    team: bool = False,
    x_github_token: Optional[str] = Header(None),
):
    """
    team=true switches from "my reviews" to "everyone's reviews for this
    repository". Gated on a live GitHub permission check (see
    _has_team_access / verify_repo_access), using a GitHub PAT supplied via
    the X-GitHub-Token header - not on "have I saved a review here before",
    which any PRScope user could trivially satisfy for any repo the shared
    backend's own token can see, regardless of their own GitHub access.
    """
    if team:
        if not repository:
            raise HTTPException(status_code=400, detail="repository is required when team=true")
        if not await _has_team_access(repository, x_github_token):
            raise HTTPException(
                status_code=403,
                detail="Team Reviews requires a GitHub Personal Access Token with access to this repository. Add one in Settings.",
            )
        query = db.query(SavedReview).filter(SavedReview.repository == repository)
    else:
        query = db.query(SavedReview).filter(SavedReview.user_id == user_id)
        if repository:
            query = query.filter(SavedReview.repository == repository)

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

    if team:
        usernames = {
            u.id: u.username
            for u in db.query(User).filter(User.id.in_({r.user_id for r in reviews})).all()
        }
        return [
            {
                "id": r.id, "user_id": r.user_id, "repository": r.repository,
                "repository_owner": r.repository_owner, "repository_name": r.repository_name,
                "pr_number": r.pr_number, "pr_title": r.pr_title, "pr_url": r.pr_url,
                "risk_score": r.risk_score, "risk_category": r.risk_category,
                "executive_summary": r.executive_summary, "review_status": r.review_status,
                "review_notes": r.review_notes, "created_at": r.created_at, "updated_at": r.updated_at,
                "last_reviewed_at": r.last_reviewed_at, "author_username": usernames.get(r.user_id),
            }
            for r in reviews
        ]

    return reviews

@router.get("/workspace/reviews/{review_id}", response_model=SavedReviewResponse)
async def get_review_detail(
    review_id: int,
    user_id: int = Depends(verify_token),
    db: Session = Depends(get_db),
    x_github_token: Optional[str] = Header(None),
):
    review = db.query(SavedReview).filter(SavedReview.id == review_id).first()
    if not review or (review.user_id != user_id and not await _has_team_access(review.repository, x_github_token)):
        raise HTTPException(status_code=404, detail="Review not found")
    return review

@router.get("/workspace/reviews/{review_id}/events", response_model=list[ReviewEventResponse])
async def get_review_events(
    review_id: int,
    user_id: int = Depends(verify_token),
    db: Session = Depends(get_db),
    x_github_token: Optional[str] = Header(None),
):
    review = db.query(SavedReview).filter(SavedReview.id == review_id).first()
    if not review or (review.user_id != user_id and not await _has_team_access(review.repository, x_github_token)):
        raise HTTPException(status_code=404, detail="Review not found")

    events = db.query(ReviewEvent).filter(ReviewEvent.review_id == review_id).order_by(ReviewEvent.timestamp.desc()).all()
    return events


@router.post("/post-comment")
async def post_comment(req: PostCommentRequest, user_id: int = Depends(verify_token)):
    try:
        res = await post_review_comment(req.repo_url, req.pr_number, req.comment_body, req.github_token)
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/post-status")
async def post_status(req: PostStatusRequest, user_id: int = Depends(verify_token)):
    """
    Publishes a commit status (visible in the PR's GitHub "Checks" section)
    reflecting a risk verdict computed from the deterministic analysis -
    a separate, explicit action from /analyze itself so running an analysis
    never silently writes to a repo the caller doesn't intend to.
    """
    try:
        sha = await fetch_pr_head_sha(req.repo_url, req.pr_number)
        res = await post_commit_status(
            repo_url=req.repo_url,
            sha=sha,
            state=req.state,
            description=req.description,
            target_url=req.target_url,
            github_token=req.github_token,
        )
        return res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ==================================================
# WEBHOOKS
# ==================================================
from fastapi import Request

webhook_debouncer = WebhookDebouncer(delay_seconds=settings.WEBHOOK_DEBOUNCE_SECONDS)

def _verify_webhook_signature(secret: str, body: bytes, signature_header: str) -> bool:
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature_header)


def _webhook_status_from_result(result: Dict[str, Any]) -> tuple:
    """
    Maps a deterministic analysis result to a commit-status (state,
    description) pair. A simpler, server-side cousin of the extension's
    getReviewDecision - there's no logged-in user or "needs test coverage"
    signal available in a webhook-triggered run, just the same underlying
    risk score / security findings / architecture violations.
    """
    risk = result["risk_score"]
    score = risk.get("score", 0)
    security_findings = result["security_findings"]
    arch_violations = result["arch_violations"]
    is_critical_sec = any(f.get("severity") == "Critical" for f in security_findings)

    if is_critical_sec or security_findings:
        return "failure", f"PRScope: {len(security_findings)} security finding(s) detected."
    if score >= 7:
        return "failure", f"PRScope: High risk ({score}/10) - review recommended before merge."
    if arch_violations:
        return "failure", f"PRScope: {len(arch_violations)} architecture violation(s) detected."
    if score >= 4:
        return "pending", f"PRScope: Moderate risk ({score}/10) - manual verification recommended."
    return "success", f"PRScope: Low risk ({score}/10). No security or architecture concerns."


async def _analyze_and_publish_status(repo_url: str, owner: str, repo: str, pr_number: int) -> None:
    """
    The actual work a debounced webhook event runs: a full deterministic
    analysis, then a commit status reflecting the verdict - using the
    shared server-side GITHUB_TOKEN, since there's no per-user PAT in a
    webhook context. Runs unattended (no request to report back to), so
    failures are logged rather than raised.
    """
    try:
        pr_data = await fetch_pr_data(repo_url, pr_number)
        result = await _run_deterministic_pipeline(pr_data, None)
        state, description = _webhook_status_from_result(result)
        await post_commit_status(
            repo_url=repo_url,
            sha=pr_data["head_sha"],
            state=state,
            description=description,
        )
    except Exception as e:
        print(f"Webhook-triggered analysis failed for {repo_url}#{pr_number}: {e}")

    # Keep an already-opted-in repo's index fresh off real PR activity,
    # instead of only refreshing on an explicit POST /index/build call.
    # Deliberately does NOT build a fresh index for a repo that never
    # opted in (building one is an explicit, heavier action - see
    # /index/build) - only refreshes one that already exists and is ready.
    repository = f"{owner}/{repo}"
    if repository in _index_builds_in_progress:
        return
    db = SessionLocal()
    try:
        existing = db.query(RepoIndex).filter(RepoIndex.repository == repository).first()
        if existing is not None and existing.status == "ready":
            _index_builds_in_progress.add(repository)
            await build_or_update_index(db, owner, repo)
    except Exception as e:
        print(f"Webhook-triggered index refresh failed for {repository}: {e}")
    finally:
        _index_builds_in_progress.discard(repository)
        db.close()


@router.post("/webhook/github")
async def github_webhook(request: Request):
    body = await request.body()

    if not settings.GITHUB_WEBHOOK_SECRET:
        # Fail closed: an unconfigured secret must not be treated as "accept
        # anything". Set GITHUB_WEBHOOK_SECRET (and configure the same value
        # on the GitHub webhook) before pointing a real webhook at this route.
        raise HTTPException(status_code=503, detail="Webhook receiver is not configured (GITHUB_WEBHOOK_SECRET is unset).")

    signature = request.headers.get("X-Hub-Signature-256", "")
    if not _verify_webhook_signature(settings.GITHUB_WEBHOOK_SECRET, body, signature):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")

    try:
        payload = json.loads(body)
    except Exception:
        return {"status": "error", "message": "Invalid JSON"}

    if "pull_request" in payload:
        action = payload.get("action")
        if action in ["opened", "synchronize", "reopened"]:
            pr_number = payload["pull_request"]["number"]
            owner = payload["repository"]["owner"]["login"]
            repo = payload["repository"]["name"]
            repo_url = payload["repository"].get("html_url") or f"https://github.com/{owner}/{repo}"

            # Debounced, not fire-and-forget-per-event: a quick series of
            # pushes fires several `synchronize` events for the same PR, and
            # each restarts this key's timer - only the last one within the
            # debounce window actually triggers analysis.
            key = f"{owner}/{repo}#{pr_number}"
            webhook_debouncer.schedule(key, lambda: _analyze_and_publish_status(repo_url, owner, repo, pr_number))

    return {"status": "received"}
