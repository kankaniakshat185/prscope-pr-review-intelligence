import re
from typing import Dict, Any, List

def classify_pr(files: List[Dict[str, Any]]) -> str:
    categories = {
        "DOCS": 0,
        "TEST": 0,
        "DEPENDENCY": 0,
        "SECURITY": 0,
        "FRONTEND": 0,
        "BACKEND": 0,
        "DATABASE": 0,
        "INFRASTRUCTURE": 0,
        "CONFIG": 0
    }
    
    for f in files:
        filename = f.get("filename", "")
        lower_name = filename.lower()
        
        # Docs
        if lower_name.startswith("docs/") or lower_name.endswith(".md") or lower_name.endswith(".txt"):
            categories["DOCS"] += 1
        # Tests
        elif "test" in lower_name or lower_name.startswith("tests/"):
            categories["TEST"] += 1
        # Dependency
        elif lower_name in ["requirements.txt", "package.json", "poetry.lock", "package-lock.json", "yarn.lock", "go.mod", "go.sum"]:
            categories["DEPENDENCY"] += 1
        # Security
        elif any(part in lower_name for part in ["auth", "security", "jwt", "token", "crypto"]):
            categories["SECURITY"] += 1
        # Config
        elif lower_name.endswith(".yml") or lower_name.endswith(".yaml") or lower_name.endswith(".json") or lower_name.endswith(".ini") or lower_name.endswith(".toml"):
            if "github" in lower_name or "docker" in lower_name or "kubernetes" in lower_name or "k8s" in lower_name:
                categories["INFRASTRUCTURE"] += 1
            else:
                categories["CONFIG"] += 1
        # Database
        elif "db" in lower_name or "database" in lower_name or "migration" in lower_name or "sql" in lower_name or "schema" in lower_name:
            categories["DATABASE"] += 1
        # Frontend
        elif lower_name.endswith(".js") or lower_name.endswith(".jsx") or lower_name.endswith(".ts") or lower_name.endswith(".tsx") or lower_name.endswith(".css") or lower_name.endswith(".html"):
            categories["FRONTEND"] += 1
        # Backend
        elif lower_name.endswith(".py") or lower_name.endswith(".go") or lower_name.endswith(".java") or lower_name.endswith(".rb") or lower_name.endswith(".php"):
            categories["BACKEND"] += 1

    total_matched = sum(categories.values())
    if total_matched == 0:
        return "MIXED"
        
    # Find the max category
    max_cat = max(categories.items(), key=lambda x: x[1])
    
    # If one category dominates (e.g. > 60%), use it. Otherwise mixed.
    if max_cat[1] / len(files) >= 0.6:
        return max_cat[0]
        
    return "MIXED"

def summarize_diff(files: List[Dict[str, Any]]) -> str:
    summary_lines = []
    
    for f in files:
        filename = f.get("filename", "")
        status = f.get("status", "modified")
        patch = f.get("patch", "")
        
        summary_lines.append(f"File: {filename} ({status})")
        
        # Extremely basic deterministic extraction from patch
        added_lines = [line[1:] for line in patch.split('\n') if line.startswith('+') and not line.startswith('+++')]
        removed_lines = [line[1:] for line in patch.split('\n') if line.startswith('-') and not line.startswith('---')]
        
        imports_changed = [line for line in added_lines + removed_lines if "import " in line or "require(" in line or "from " in line]
        if imports_changed:
            summary_lines.append("  Imports Changed: Yes")
            
        functions_changed = [line for line in added_lines + removed_lines if line.strip().startswith("def ") or line.strip().startswith("class ") or line.strip().startswith("function ")]
        if functions_changed:
            summary_lines.append(f"  Logic Changed: {', '.join(set(functions_changed))[:200]}...")
            
        if filename.endswith(".md"):
            summary_lines.append("  Impact: Documentation only")
            
    return "\n".join(summary_lines)

def build_pr_context(pr_data: Dict[str, Any], risk_score: Dict[str, Any] = None, impact_analysis: Dict[str, Any] = None, arch_violations: List[Dict[str, Any]] = None) -> Dict[str, Any]:
    files = pr_data.get("files", [])
    
    pr_type = classify_pr(files)
    changed_files = [f.get("filename", "") for f in files]
    file_extensions = list(set([f.split(".")[-1] for f in changed_files if "." in f]))
    
    dirs_touched = list(set([f.rsplit("/", 1)[0] for f in changed_files if "/" in f]))
    
    diff_summary = summarize_diff(files)
    
    return {
        "pr_type": pr_type,
        "changed_files": changed_files,
        "file_extensions": file_extensions,
        "directories_touched": dirs_touched,
        "diff_summary": diff_summary,
        "risk_factors": risk_score.get("factor_breakdown", []) if risk_score else [],
        "risk_score": risk_score.get("score", 0) if risk_score else 0,
        "risk_category": risk_score.get("category", "Unknown") if risk_score else "Unknown",
        "impact_analysis": impact_analysis or {},
        "architecture_violations": arch_violations or [],
        "file_count": pr_data.get("changed_files", 0),
        "lines_added": pr_data.get("additions", 0),
        "lines_deleted": pr_data.get("deletions", 0)
    }
