import yaml
import os
from typing import Dict, Any, List

DEFAULT_RULES = """
auth:
  cannot_import:
    - payment
frontend:
  cannot_import:
    - database
"""

def get_architecture_rules() -> Dict[str, Any]:
    # In a real app, we might fetch this from the repo itself (.prcopilot.yml)
    # For now, we use a default
    return yaml.safe_load(DEFAULT_RULES)

def validate_architecture(pr_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    rules = get_architecture_rules()
    violations = []
    
    files = pr_data.get("files", [])
    
    for f in files:
        filename = f.get("filename", "")
        patch = f.get("patch", "")
        
        # Check simple string inclusions in the patch
        for module, rule in rules.items():
            if filename.startswith(f"{module}/") or f"/{module}/" in filename:
                cannot_import = rule.get("cannot_import", [])
                for restricted in cannot_import:
                    # simplistic check: if restricted module string is in patch additions
                    if restricted in patch:
                        violations.append({
                            "file": filename,
                            "rule": f"{module} cannot import {restricted}",
                            "explanation": f"Found reference to '{restricted}' in {module} module."
                        })
                        
    return violations
