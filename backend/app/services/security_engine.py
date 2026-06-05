import re
import ast

def analyze_security(files_changed: list) -> list:
    """
    Deterministic security analysis using Regex and AST.
    """
    findings = []
    
    # Simple regex rules for immediate matching
    regex_rules = [
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
        (re.compile(r'f["\'].*(?i)(SELECT|UPDATE|INSERT|DELETE).*\{.*\}.*["\']'), "SQL Injection", "Critical", "Potential SQL Injection via f-string interpolation.")
    ]

    for f in files_changed:
        filename = f.get("filename", "")
        # Do not run security analysis on documentation files
        if filename.endswith(".md") or filename.endswith(".txt") or "docs/" in filename:
            continue
            
        patch = f.get("patch", "")
        if not patch:
            continue
            
        # Analyze patch lines that were added (+)
        added_lines = [line[1:] for line in patch.split("\n") if line.startswith("+") and not line.startswith("+++")]
        
        for line in added_lines:
            for rule_regex, rule_name, severity, reason in regex_rules:
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
