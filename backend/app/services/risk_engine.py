from typing import Dict, Any, List, Optional
from app.services.scoring_constants import (
    LOC_MASSIVE, LOC_LARGE, LOC_MODERATE,
    FILES_MASSIVE, FILES_LARGE, FILES_MODERATE,
    SYMBOLS_LARGE, SYMBOLS_MODERATE,
    CALLERS_HIGH, CALLERS_MODERATE,
    SERVICES_WIDESPREAD,
    COMPLEXITY_VERY_HIGH, COMPLEXITY_HIGH, COMPLEXITY_MODERATE,
    CRITICAL_DIRS,
    RISK_HIGH_THRESHOLD, RISK_MEDIUM_THRESHOLD,
)

LOC_LARGE_NO_TESTS_THRESHOLD = 500  # separate from LOC_LARGE (501): this gates the "no tests on a large change" penalty specifically

def calculate_risk(
    pr_data: Dict[str, Any],
    pr_type: str,
    changed_symbols: Dict[str, List[str]],
    dependency_impact: Dict[str, Any],
    security_findings: List[Dict[str, Any]],
    architecture_violations: List[Dict[str, Any]],
    complexity_data: Optional[Dict[str, int]] = None
) -> Dict[str, Any]:
    score = 0
    factors = []
    
    if pr_type == "DOCS":
        return {
            "score": 0,
            "category": "Low Risk",
            "factor_breakdown": []
        }
    
    additions = pr_data.get("additions", 0)
    deletions = pr_data.get("deletions", 0)
    total_loc = additions + deletions
    changed_files = pr_data.get("changed_files", 0)
    files = pr_data.get("files", [])
    
    # 1. LOC Scoring
    if total_loc >= LOC_MASSIVE:
        score += 3
        factors.append({"name": "Massive LOC Change", "weight": 3, "reason": f"{total_loc} lines changed"})
    elif total_loc >= LOC_LARGE:
        score += 2
        factors.append({"name": "Large LOC Change", "weight": 2, "reason": f"{total_loc} lines changed"})
    elif total_loc >= LOC_MODERATE:
        score += 1
        factors.append({"name": "Moderate LOC Change", "weight": 1, "reason": f"{total_loc} lines changed"})

    # 2. Files Changed
    if changed_files >= FILES_MASSIVE:
        score += 3
        factors.append({"name": "Massive File Surface", "weight": 3, "reason": f"{changed_files} files changed"})
    elif changed_files >= FILES_LARGE:
        score += 2
        factors.append({"name": "Large File Surface", "weight": 2, "reason": f"{changed_files} files changed"})
    elif changed_files >= FILES_MODERATE:
        score += 1
        factors.append({"name": "Moderate File Surface", "weight": 1, "reason": f"{changed_files} files changed"})

    # 3. Critical Path Scoring
    critical_dirs = CRITICAL_DIRS
    touched_critical = set()
    has_tests = False
    
    for f in files:
        filename = f.get("filename", "")
        if "test" in filename.lower() or filename.startswith("tests/"):
            has_tests = True
        
        for d in critical_dirs:
            if f"/{d}/" in filename or filename.startswith(f"{d}/") or d in filename.split("/"):
                touched_critical.add(d)
                
    if len(touched_critical) > 1:
        score += 3
        factors.append({"name": "Multiple Critical Paths Modified", "weight": 3, "reason": f"Modified: {', '.join(touched_critical)}"})
    elif len(touched_critical) == 1:
        score += 2
        factors.append({"name": "Critical Path Modified", "weight": 2, "reason": f"Modified: {list(touched_critical)[0]}"})
        
    # 4. Test Coverage Signal
    if pr_type in ["BACKEND", "FRONTEND", "SECURITY", "DATABASE", "INFRASTRUCTURE", "MIXED"]:
        if total_loc > 0 and not has_tests:
            if total_loc > LOC_LARGE_NO_TESTS_THRESHOLD:
                score += 2
                factors.append({"name": "No Tests Updated (Large Change)", "weight": 2, "reason": "No test files modified for >500 LOC change"})
            else:
                score += 1
                factors.append({"name": "No Tests Updated", "weight": 1, "reason": "No test files modified"})
                
    # 5. Architecture Violations
    if architecture_violations:
        arch_pts = min(len(architecture_violations) * 2, 3)
        score += arch_pts
        factors.append({"name": "Architecture Violations", "weight": arch_pts, "reason": f"{len(architecture_violations)} violations detected"})
        
    # 6. Security Findings Integration
    sec_pts = 0
    high_sev_names = []
    for sf in security_findings:
        sev = sf.get("severity", "Low")
        if sev == "Critical":
            sec_pts += 3
            high_sev_names.append(sf.get("name", "Unknown"))
        elif sev == "High":
            sec_pts += 2
            high_sev_names.append(sf.get("name", "Unknown"))
        elif sev == "Medium":
            sec_pts += 1
            high_sev_names.append(sf.get("name", "Unknown"))
            
    if sec_pts > 0:
        sec_pts = min(sec_pts, 3)
        score += sec_pts
        factors.append({"name": "Security Findings", "weight": sec_pts, "reason": f"Findings detected: {', '.join(high_sev_names[:2])}{'...' if len(high_sev_names)>2 else ''}"})
        
    # 7. Changed Symbol Analysis
    num_symbols = 0
    num_symbols += len(changed_symbols.get("functions_modified", []))
    num_symbols += len(changed_symbols.get("functions_added", []))
    num_symbols += len(changed_symbols.get("functions_removed", []))
    num_symbols += len(changed_symbols.get("classes_modified", []))
    
    if num_symbols >= SYMBOLS_LARGE:
        score += 2
        factors.append({"name": "Large Symbol Surface", "weight": 2, "reason": f"{num_symbols} symbols modified"})
    elif num_symbols >= SYMBOLS_MODERATE:
        score += 1
        factors.append({"name": "Moderate Symbol Surface", "weight": 1, "reason": f"{num_symbols} symbols modified"})

    # 7b. Cyclomatic Complexity (McCabe, computed from an actual control-flow
    # graph - see complexity_engine.py). A genuine static-analysis metric
    # rather than a LOC-based proxy for "how complicated is this function."
    if complexity_data:
        most_complex_fn = max(complexity_data, key=complexity_data.get)
        max_complexity = complexity_data[most_complex_fn]
        if max_complexity >= COMPLEXITY_VERY_HIGH:
            score += 3
            factors.append({"name": "Very High Cyclomatic Complexity", "weight": 3, "reason": f"'{most_complex_fn}' has cyclomatic complexity {max_complexity}"})
        elif max_complexity >= COMPLEXITY_HIGH:
            score += 2
            factors.append({"name": "High Cyclomatic Complexity", "weight": 2, "reason": f"'{most_complex_fn}' has cyclomatic complexity {max_complexity}"})
        elif max_complexity >= COMPLEXITY_MODERATE:
            score += 1
            factors.append({"name": "Moderate Cyclomatic Complexity", "weight": 1, "reason": f"'{most_complex_fn}' has cyclomatic complexity {max_complexity}"})

    # 8. Dependency Impact Scoring
    dep_graph = dependency_impact.get("dependency_graph", {})
    downstream_callers = set()
    for func in dep_graph.get("modified_functions", []):
        for caller in func.get("called_by", []):
            downstream_callers.add(caller)
            
    num_callers = len(downstream_callers)
    if num_callers >= CALLERS_HIGH:
        score += 2
        factors.append({"name": "High Dependency Impact", "weight": 2, "reason": f"{num_callers} downstream callers affected"})
    elif num_callers >= CALLERS_MODERATE:
        score += 1
        factors.append({"name": "Moderate Dependency Impact", "weight": 1, "reason": f"{num_callers} downstream callers affected"})
        
    # 9. Multi-Service Impact
    affected_services = dependency_impact.get("affected_services", [])
    num_services = len(affected_services)
    if num_services >= SERVICES_WIDESPREAD:
        score += 2
        factors.append({"name": "Widespread Service Impact", "weight": 2, "reason": f"{num_services} services impacted"})
    elif num_services == 2:
        score += 1
        factors.append({"name": "Multi-Service Impact", "weight": 1, "reason": "2 services impacted"})
        
    # 10. Risk Normalization & Categories
    score = min(10, score)
    
    if score >= RISK_HIGH_THRESHOLD:
        category = "High Risk"
    elif score >= RISK_MEDIUM_THRESHOLD:
        category = "Medium Risk"
    else:
        category = "Low Risk"
        
    return {
        "score": score,
        "category": category,
        "factor_breakdown": factors
    }
