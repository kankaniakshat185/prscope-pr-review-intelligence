from app.services.risk_engine import calculate_risk

EMPTY_SYMBOLS = {"functions_modified": [], "functions_added": [], "functions_removed": [], "classes_modified": []}


def base_pr(**overrides):
    pr = {"additions": 10, "deletions": 5, "changed_files": 2, "files": []}
    pr.update(overrides)
    return pr


def test_docs_pr_is_always_low_risk_regardless_of_size():
    result = calculate_risk(
        pr_data=base_pr(additions=5000, deletions=5000, changed_files=200),
        pr_type="DOCS",
        changed_symbols=EMPTY_SYMBOLS,
        dependency_impact={},
        security_findings=[],
        architecture_violations=[],
    )
    assert result["score"] == 0
    assert result["category"] == "Low Risk"
    assert result["factor_breakdown"] == []


def test_massive_loc_change_is_flagged():
    pr = base_pr(additions=800, deletions=300)  # total 1100 >= 1000
    result = calculate_risk(pr, "BACKEND", EMPTY_SYMBOLS, {}, [], [])
    assert any(f["name"] == "Massive LOC Change" for f in result["factor_breakdown"])


def test_critical_path_modification_is_flagged():
    pr = base_pr(files=[{"filename": "backend/auth/login.py"}])
    result = calculate_risk(pr, "BACKEND", EMPTY_SYMBOLS, {}, [], [])
    assert any("Critical Path" in f["name"] for f in result["factor_breakdown"])


def test_critical_security_finding_raises_score():
    pr = base_pr()
    findings = [{"name": "Hardcoded Secrets", "severity": "Critical"}]
    result = calculate_risk(pr, "BACKEND", EMPTY_SYMBOLS, {}, findings, [])
    assert any(f["name"] == "Security Findings" for f in result["factor_breakdown"])
    assert result["category"] in ("Low Risk", "Medium Risk", "High Risk")


def test_score_is_capped_at_ten_even_when_every_factor_fires():
    pr = base_pr(
        additions=5000, deletions=5000, changed_files=100,
        files=[{"filename": f"backend/auth/f{i}.py"} for i in range(5)],
    )
    symbols = {"functions_modified": [f"f{i}" for i in range(15)], "functions_added": [], "functions_removed": [], "classes_modified": []}
    dependency_impact = {"dependency_graph": {"modified_functions": []}, "affected_services": ["a", "b", "c"]}
    findings = [{"name": "x", "severity": "Critical"}] * 5
    violations = [{"rule": "x"}] * 5

    result = calculate_risk(pr, "BACKEND", symbols, dependency_impact, findings, violations)
    assert result["score"] <= 10
    assert result["category"] == "High Risk"
