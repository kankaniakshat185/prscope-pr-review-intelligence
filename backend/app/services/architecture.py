import yaml
import re
from typing import Dict, Any, List

DEFAULT_RULES = """
auth:
  cannot_import:
    - payment
frontend:
  cannot_import:
    - database
"""

def get_architecture_rules(rules_yaml: str = None) -> Dict[str, Any]:
    if rules_yaml:
        try:
            return yaml.safe_load(rules_yaml)
        except Exception:
            pass
    return yaml.safe_load(DEFAULT_RULES)

def validate_architecture(pr_data: Dict[str, Any], rules_yaml: str = None) -> List[Dict[str, Any]]:
    rules = get_architecture_rules(rules_yaml)
    violations = []
    
    files = pr_data.get("files", [])
    
    for f in files:
        filename = f.get("filename", "")
        patch = f.get("patch", "")
        
        # Only check added lines
        added_lines = [
            line[1:] for line in patch.split('\\n') 
            if line.startswith('+') and not line.startswith('+++')
        ]
        
        for module, rule in rules.items():
            if filename.startswith(f"{module}/") or f"/{module}/" in filename:
                cannot_import = rule.get("cannot_import", [])
                for restricted in cannot_import:
                    # Construct regex pattern to match imports in Python or JS/TS
                    # Python: import X, from X import ...
                    # JS/TS: import ... from 'X', require('X')
                    # We look for the restricted module name bounded by word boundaries or quotes
                    pattern = re.compile(
                        r'^(?:import\s+.*?\b{0}\b|from\s+\b{0}\b\s+import|.*?require\s*\(\s*[\'"]{0}[\'"]\s*\)|import\s+.*?\s+from\s+[\'"]{0}[\'"])'.format(re.escape(restricted)),
                        re.IGNORECASE
                    )
                    
                    for line in added_lines:
                        if pattern.search(line.strip()):
                            violations.append({
                                "file": filename,
                                "rule": f"{module} cannot import {restricted}",
                                "explanation": f"Found direct import of '{restricted}' in {module} module."
                            })
                            break # Once found in this file, we can move on to the next rule/file
                        
    return violations
