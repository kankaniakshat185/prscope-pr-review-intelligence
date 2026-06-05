from typing import Dict, Any

def calculate_risk(pr_data: Dict[str, Any]) -> Dict[str, Any]:
    score = 0
    factors = []
    
    additions = pr_data.get("additions", 0)
    deletions = pr_data.get("deletions", 0)
    total_loc = additions + deletions
    changed_files = pr_data.get("changed_files", 0)
    files = pr_data.get("files", [])
    
    # Rule 1: LOC changed
    if total_loc > 1000:
        score += 3
        factors.append({"name": "High LOC changed", "weight": 3, "reason": f"{total_loc} lines changed"})
    elif total_loc > 300:
        score += 1
        factors.append({"name": "Moderate LOC changed", "weight": 1, "reason": f"{total_loc} lines changed"})
        
    # Rule 2: Files changed
    if changed_files > 20:
        score += 2
        factors.append({"name": "Many files changed", "weight": 2, "reason": f"{changed_files} files changed"})
        
    # Rule 3: Critical directories
    critical_dirs = ["core", "auth", "payment", "security"]
    touched_critical = []
    has_tests = False
    
    for f in files:
        filename = f.get("filename", "")
        if "test" in filename.lower():
            has_tests = True
        
        for d in critical_dirs:
            if f"/{d}/" in filename or filename.startswith(f"{d}/"):
                if d not in touched_critical:
                    touched_critical.append(d)
                    
    if touched_critical:
        score += 3
        factors.append({"name": "Critical directories touched", "weight": 3, "reason": f"Modified: {', '.join(touched_critical)}"})
        
    # Rule 4: Tests
    if total_loc > 100 and not has_tests:
        score += 2
        factors.append({"name": "No tests modified", "weight": 2, "reason": "No test files detected in a large change"})
        
    # Normalize score
    score = min(10, score)
    
    if score >= 7:
        category = "High Risk"
    elif score >= 4:
        category = "Medium Risk"
    else:
        category = "Low Risk"
        
    return {
        "score": score,
        "category": category,
        "factor_breakdown": factors
    }
