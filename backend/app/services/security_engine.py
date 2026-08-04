import ast
import json
import os as _os
import re
import subprocess
import sys
import tempfile
from typing import Any, Dict, List, Optional

# Regex rules remain the detection path for non-Python files (JS/TS, etc.)
# and as a fallback when a Python diff fragment doesn't parse cleanly enough
# for bandit to run against it. For .py files, bandit (see below) replaces
# these entirely - it's a mature, actively-maintained security linter with
# far fewer false positives than hand-rolled single-line regex.
REGEX_RULES = [
    # Hardcoded Credentials
    (re.compile(r'(?i)(password|passwd|pwd)\s*=\s*["\'][^"\']+["\']'), "Hardcoded Credentials", "High", "Password assigned directly in code."),
    (re.compile(r'(?i)(api_key|apikey|secret|token)\s*=\s*["\'][^"\']+["\']'), "Hardcoded Secrets", "Critical", "API key or secret hardcoded in code."),
    # Unsafe Exec
    (re.compile(r'\beval\s*\('), "Unsafe Dynamic Execution", "Critical", "Use of eval() detected."),
    (re.compile(r'\bexec\s*\('), "Unsafe Dynamic Execution", "Critical", "Use of exec() detected."),
    # Command Injection
    (re.compile(r'os\.system\s*\('), "Command Injection", "High", "Use of os.system() detected."),
    (re.compile(r'subprocess\.(Popen|call|run)\s*\([^)]*shell\s*=\s*True'), "Command Injection", "High", "subprocess called with shell=True."),
    # Unsafe Deserialization
    (re.compile(r'pickle\.loads\s*\('), "Unsafe Deserialization", "High", "Use of pickle.loads() detected."),
    (re.compile(r'yaml\.load\s*\('), "Unsafe Deserialization", "High", "Use of yaml.load() detected. Prefer yaml.safe_load()."),
    # SQL Injection (f-strings with SELECT/UPDATE/INSERT/DELETE)
    (re.compile(r'(?i)f["\'].*(SELECT|UPDATE|INSERT|DELETE).*\{.*\}.*["\']'), "SQL Injection", "Critical", "Potential SQL Injection via f-string interpolation.")
]


def _map_bandit_severity(severity: str, confidence: str) -> str:
    if severity == "HIGH" and confidence == "HIGH":
        return "Critical"
    if severity == "HIGH" or (severity == "MEDIUM" and confidence == "HIGH"):
        return "High"
    if severity == "MEDIUM":
        return "Medium"
    return "Low"


def _map_bandit_confidence(confidence: str) -> int:
    return {"HIGH": 90, "MEDIUM": 70, "LOW": 50}.get(confidence, 60)


def _bandit_finding_name(test_name: str, test_id: str) -> str:
    # Several bandit checks share the generic test_name "blacklist" (e.g. for
    # blacklisted imports/calls) - not useful as a label on its own.
    if test_name == "blacklist":
        return f"Blacklisted Call or Import ({test_id})"
    return test_name.replace("_", " ").title()


def _bandit_scan_python(filename: str, patch: str) -> Optional[List[Dict[str, Any]]]:
    """
    Run bandit against the added lines of a Python file's diff.

    Returns None (signalling the caller to fall back to REGEX_RULES) if the
    reconstructed diff fragment doesn't parse as valid Python, or if bandit
    itself can't be run for any reason - diff fragments aren't always
    syntactically complete on their own, same limitation as elsewhere in
    this codebase's diff-based analysis.
    """
    lines: List[str] = []
    is_added: List[bool] = []
    for line in patch.split("\n"):
        if line.startswith("+") and not line.startswith("+++"):
            lines.append(line[1:])
            is_added.append(True)
        elif line.startswith(" "):
            lines.append(line[1:])
            is_added.append(False)
        # removed lines and diff metadata are dropped entirely

    source = "\n".join(lines)
    if not source.strip():
        return []

    try:
        ast.parse(source)
    except SyntaxError:
        return None

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as tmp:
            tmp.write(source)
            tmp_path = tmp.name

        result = subprocess.run(
            [sys.executable, "-m", "bandit", "-f", "json", tmp_path],
            capture_output=True, text=True, timeout=15
        )
        report = json.loads(result.stdout)
    except (subprocess.TimeoutExpired, json.JSONDecodeError, FileNotFoundError, OSError) as e:
        print(f"Bandit scan failed for {filename}, falling back to regex rules: {e}")
        return None
    finally:
        if tmp_path and _os.path.exists(tmp_path):
            _os.unlink(tmp_path)

    findings = []
    for issue in report.get("results", []):
        line_idx = issue.get("line_number", 0) - 1
        if line_idx < 0 or line_idx >= len(is_added) or not is_added[line_idx]:
            continue  # only flag issues on lines actually added in this diff

        severity = issue.get("issue_severity", "LOW")
        confidence = issue.get("issue_confidence", "LOW")
        test_id = issue.get("test_id", "")

        findings.append({
            "name": _bandit_finding_name(issue.get("test_name", "issue"), test_id),
            "severity": _map_bandit_severity(severity, confidence),
            "file": filename,
            "confidence": _map_bandit_confidence(confidence),
            "reason": issue.get("issue_text", "").strip(),
            "recommendation": f"Review and remediate. Bandit check {test_id}: {issue.get('more_info', '')}",
            "snippet": lines[line_idx].strip() if line_idx < len(lines) else "",
        })

    return findings


def analyze_security(files_changed: list) -> list:
    """
    Deterministic security analysis for Python files: bandit plus the regex
    rules, unioned (not either/or). Bandit is far broader than our regex
    rules, but it is NOT a strict superset of them - verified empirically it
    has no check at all for generic API_KEY/SECRET/TOKEN-style hardcoded
    credential variable names (only password-named variables), and misses
    yaml.load() in isolation. Replacing the regex rules outright would have
    silently regressed exactly the kind of hardcoded-secret detection this
    codebase's own audit relied on. So: bandit runs first, then the regex
    rules run too but skip any line bandit already flagged, to avoid
    duplicate findings for the same line.

    For non-Python files (JS/TS, etc.) or Python fragments bandit can't
    parse, the regex rules are the only detector, same as before.
    """
    findings = []

    for f in files_changed:
        filename = f.get("filename", "")
        # Do not run security analysis on documentation files
        if filename.endswith(".md") or filename.endswith(".txt") or "docs/" in filename:
            continue

        patch = f.get("patch", "")
        if not patch:
            continue

        added_lines = [line[1:] for line in patch.split("\n") if line.startswith("+") and not line.startswith("+++")]
        lines_flagged_by_bandit = set()

        if filename.endswith(".py"):
            bandit_findings = _bandit_scan_python(filename, patch)
            if bandit_findings is not None:
                for finding in bandit_findings:
                    lines_flagged_by_bandit.add(finding["snippet"])
                    if finding not in findings:
                        findings.append(finding)

        for line in added_lines:
            if line.strip() in lines_flagged_by_bandit:
                continue
            for rule_regex, rule_name, severity, reason in REGEX_RULES:
                if rule_regex.search(line):
                    finding = {
                        "name": rule_name,
                        "severity": severity,
                        "file": filename,
                        "confidence": 95,
                        "reason": reason,
                        "recommendation": "Review and remediate immediately. Use safe alternatives or parameterized queries.",
                        "snippet": line.strip()
                    }
                    if finding not in findings:
                        findings.append(finding)

    return findings
