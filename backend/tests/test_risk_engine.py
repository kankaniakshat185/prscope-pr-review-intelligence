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
    complexity = {"f0": 30}

    result = calculate_risk(pr, "BACKEND", symbols, dependency_impact, findings, violations, complexity_data=complexity)
    assert result["score"] <= 10
    assert result["category"] == "High Risk"


def test_no_complexity_data_adds_no_factor():
    pr = base_pr()
    result = calculate_risk(pr, "BACKEND", EMPTY_SYMBOLS, {}, [], [], complexity_data=None)
    assert not any("Complexity" in f["name"] for f in result["factor_breakdown"])


def test_very_high_complexity_is_flagged_with_the_offending_function_named():
    pr = base_pr()
    result = calculate_risk(pr, "BACKEND", EMPTY_SYMBOLS, {}, [], [], complexity_data={"tangled_function": 18})
    factor = next(f for f in result["factor_breakdown"] if f["name"] == "Very High Cyclomatic Complexity")
    assert factor["weight"] == 3
    assert "tangled_function" in factor["reason"]
    assert "18" in factor["reason"]


def test_moderate_complexity_is_flagged_at_a_lower_weight():
    pr = base_pr()
    result = calculate_risk(pr, "BACKEND", EMPTY_SYMBOLS, {}, [], [], complexity_data={"foo": 7})
    factor = next(f for f in result["factor_breakdown"] if f["name"] == "Moderate Cyclomatic Complexity")
    assert factor["weight"] == 1


def test_low_complexity_does_not_trigger_the_factor():
    pr = base_pr()
    result = calculate_risk(pr, "BACKEND", EMPTY_SYMBOLS, {}, [], [], complexity_data={"foo": 2})
    assert not any("Complexity" in f["name"] for f in result["factor_breakdown"])


def test_most_complex_function_is_the_one_named_when_multiple_are_present():
    pr = base_pr()
    result = calculate_risk(
        pr, "BACKEND", EMPTY_SYMBOLS, {}, [], [],
        complexity_data={"simple_fn": 2, "worst_fn": 20, "medium_fn": 8},
    )
    factor = next(f for f in result["factor_breakdown"] if f["name"] == "Very High Cyclomatic Complexity")
    assert "worst_fn" in factor["reason"]
