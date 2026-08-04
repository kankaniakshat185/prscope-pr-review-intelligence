from app.services.security_engine import analyze_security


def test_detects_hardcoded_secret():
    files = [{"filename": "app/config.py", "patch": '+API_KEY = "sk-abcdef1234567890"\n'}]
    findings = analyze_security(files)
    assert any(f["name"] == "Hardcoded Secrets" for f in findings)


def test_detects_eval_usage():
    # For Python files this is now bandit's finding (test B307), not our old
    # regex rule - bandit already flagged this exact line, so the regex rule
    # correctly steps aside rather than producing a duplicate.
    files = [{"filename": "app/utils.py", "patch": "+result = eval(user_input)\n"}]
    findings = analyze_security(files)
    assert len(findings) == 1
    assert "B307" in findings[0]["name"]
    assert findings[0]["severity"] == "High"
    assert "eval" in findings[0]["reason"].lower()


def test_detects_shell_true():
    # Bandit's B602 check (subprocess with shell=True), not our old regex
    # rule - same "bandit flagged it, regex steps aside" behavior as above.
    files = [{"filename": "app/run.py", "patch": "+subprocess.run(cmd, shell=True)\n"}]
    findings = analyze_security(files)
    assert len(findings) == 1
    assert findings[0]["severity"] == "Critical"
    assert "shell" in findings[0]["reason"].lower()


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


def test_yaml_load_is_still_caught_even_though_bandit_misses_it_standalone():
    # Verified empirically: bandit does not flag a bare `yaml.load(x)` call
    # in an isolated diff fragment the way it does in a full file. The regex
    # rule is what actually catches this case for Python files.
    files = [{"filename": "app/config.py", "patch": "+data = yaml.load(user_input)\n"}]
    findings = analyze_security(files)
    assert any(f["name"] == "Unsafe Deserialization" for f in findings)


def test_bandit_and_regex_do_not_both_flag_the_same_line():
    # A line bandit already caught (subprocess+shell=True, via B602) should
    # not also produce a second, redundant finding from the regex rule that
    # covers the same pattern.
    files = [{"filename": "app/run.py", "patch": "+subprocess.run(cmd, shell=True)\n"}]
    findings = analyze_security(files)
    assert len(findings) == 1
