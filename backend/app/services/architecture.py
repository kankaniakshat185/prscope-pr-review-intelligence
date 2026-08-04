import ast
import yaml
import re
from typing import Dict, Any, List, Optional

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


def _python_import_violations(
    patch: str, filename: str, module: str, restricted_names: List[str]
) -> Optional[List[Dict[str, Any]]]:
    """
    AST-based import detection for Python files. More precise than regex:
    only flags import statements that were genuinely added in the diff, and
    - unlike line-by-line text matching - correctly ignores the restricted
    name appearing inside a comment, docstring, or unrelated string literal.

    Returns None (signalling the caller to fall back to regex) if the
    reconstructed source doesn't parse - diff fragments aren't always
    syntactically complete on their own.
    """
    lines: List[str] = []
    is_added: List[bool] = []
    for line in patch.split('\n'):
        if line.startswith('+') and not line.startswith('+++'):
            lines.append(line[1:])
            is_added.append(True)
        elif line.startswith(' '):
            lines.append(line[1:])
            is_added.append(False)
        # removed lines (-) and diff metadata (@@/---/+++) are dropped entirely

    source = "\n".join(lines)
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None

    violations = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.Import, ast.ImportFrom)):
            continue

        line_idx = node.lineno - 1
        if line_idx >= len(is_added) or not is_added[line_idx]:
            continue  # only flag imports that were actually added, not pre-existing context

        if isinstance(node, ast.Import):
            imported_names = [alias.name.split(".")[0] for alias in node.names]
        else:
            imported_names = [node.module.split(".")[0]] if node.module else []

        for name in imported_names:
            if name in restricted_names:
                violations.append({
                    "file": filename,
                    "rule": f"{module} cannot import {name}",
                    "explanation": f"Found direct import of '{name}' in {module} module."
                })
                break  # one violation per file/rule match is enough, matches prior behavior

    return violations


def validate_architecture(pr_data: Dict[str, Any], rules_yaml: str = None) -> List[Dict[str, Any]]:
    rules = get_architecture_rules(rules_yaml)
    violations = []

    files = pr_data.get("files", [])

    for f in files:
        filename = f.get("filename", "")
        patch = f.get("patch", "")

        # Only check added lines
        added_lines = [
            line[1:] for line in patch.split('\n')
            if line.startswith('+') and not line.startswith('+++')
        ]

        for module, rule in rules.items():
            if filename.startswith(f"{module}/") or f"/{module}/" in filename:
                cannot_import = rule.get("cannot_import", [])
                if not cannot_import:
                    continue

                if filename.endswith(".py"):
                    ast_violations = _python_import_violations(patch, filename, module, cannot_import)
                    if ast_violations is not None:
                        violations.extend(ast_violations)
                        continue  # AST parsing succeeded - skip the regex fallback for this file

                # Regex fallback: non-Python files (JS/TS via require()/import),
                # or Python fragments that didn't parse cleanly on their own.
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
