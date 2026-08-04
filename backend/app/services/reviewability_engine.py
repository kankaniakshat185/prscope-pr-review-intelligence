from typing import Dict, Any, List
from app.services.scoring_constants import (
    LOC_REVIEWABLE_SMALL, LOC_REVIEWABLE_MEDIUM, LOC_REVIEWABLE_LARGE,
    FILES_REVIEWABLE_FEW,
    DESCRIPTION_GOOD_LENGTH,
)

def calculate_reviewability(
    pr_data: Dict[str, Any],
    security_findings: List[Dict[str, Any]],
    architecture_violations: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Calculate reviewability score (0-10).
    Higher is better (more reviewable).
    """
    score = 0
    factors = []
    
    # 1. PR Description
    desc = pr_data.get("description", "")
    if desc and len(desc) > DESCRIPTION_GOOD_LENGTH:
        score += 2
        factors.append({"name": "Good PR description", "weight": 2, "reason": "Description is present and sufficiently detailed."})
    elif desc:
        score += 1
        factors.append({"name": "Basic PR description", "weight": 1, "reason": "Description is very brief."})
    else:
        factors.append({"name": "No PR description", "weight": 0, "reason": "Missing description makes review harder."})
        
    # 2. Tests Present
    files = pr_data.get("files", [])
    has_tests = any("test" in f.get("filename", "").lower() or f.get("filename", "").startswith("tests/") for f in files)
    if has_tests:
        score += 2
        factors.append({"name": "Tests included", "weight": 2, "reason": "Test modifications/additions detected."})
    else:
        factors.append({"name": "No tests", "weight": 0, "reason": "No test files were modified."})
        
    # 3. PR Size (LOC)
    additions = pr_data.get("additions", 0)
    deletions = pr_data.get("deletions", 0)
    total_loc = additions + deletions
    
    if total_loc < LOC_REVIEWABLE_SMALL:
        score += 3
        factors.append({"name": "Very small scope", "weight": 3, "reason": f"Only {total_loc} lines changed."})
    elif total_loc < LOC_REVIEWABLE_MEDIUM:
        score += 2
        factors.append({"name": "Small scope", "weight": 2, "reason": f"Only {total_loc} lines changed."})
    elif total_loc < LOC_REVIEWABLE_LARGE:
        score += 1
        factors.append({"name": "Medium scope", "weight": 1, "reason": f"{total_loc} lines changed."})
    else:
        factors.append({"name": "Massive scope", "weight": 0, "reason": f"{total_loc} lines changed makes review difficult."})
        
    # 4. Number of Files
    changed_files = pr_data.get("changed_files", 0)
    if changed_files < FILES_REVIEWABLE_FEW:
        score += 1
        factors.append({"name": "Few files changed", "weight": 1, "reason": f"Only {changed_files} files changed."})
    else:
        factors.append({"name": "Many files changed", "weight": 0, "reason": f"{changed_files} files changed."})
        
    # 5. Security & Architecture
    if not security_findings:
        score += 1
        factors.append({"name": "No security findings", "weight": 1, "reason": "No deterministic security issues."})
    else:
        factors.append({"name": "Security findings present", "weight": 0, "reason": "Security issues complicate the review."})
        
    if not architecture_violations:
        score += 1
        factors.append({"name": "No architecture violations", "weight": 1, "reason": "No architectural constraints violated."})
        
    score = min(10, score)
    
    return {
        "score": score,
        "factor_breakdown": factors
    }
