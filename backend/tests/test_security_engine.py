from app.services.security_engine import analyze_security


def test_detects_hardcoded_secret():
    files = [{"filename": "app/config.py", "patch": '+API_KEY = "sk-abcdef1234567890"\n'}]
    findings = analyze_security(files)
    assert any(f["name"] == "Hardcoded Secrets" for f in findings)


def test_detects_eval_usage():
    files = [{"filename": "app/utils.py", "patch": "+result = eval(user_input)\n"}]
    findings = analyze_security(files)
    assert any(f["name"] == "Unsafe Dynamic Execution" for f in findings)


def test_detects_shell_true():
    files = [{"filename": "app/run.py", "patch": "+subprocess.run(cmd, shell=True)\n"}]
    findings = analyze_security(files)
    assert any(f["name"] == "Command Injection" for f in findings)


def test_skips_documentation_files_entirely():
    files = [{"filename": "docs/setup.md", "patch": '+API_KEY = "sk-abcdef1234567890"\n'}]
    assert analyze_security(files) == []


def test_clean_code_has_no_findings():
    files = [{"filename": "app/math_utils.py", "patch": "+def add(a, b):\n+    return a + b\n"}]
    assert analyze_security(files) == []


def test_only_added_lines_are_scanned_not_removed_lines():
    files = [{"filename": "app/config.py", "patch": '-API_KEY = "sk-abcdef1234567890"\n+API_KEY = os.environ["API_KEY"]\n'}]
    findings = analyze_security(files)
    assert findings == []
