from app.services.reviewability_engine import calculate_reviewability


def test_small_well_described_tested_pr_scores_high():
    pr = {
        "description": "This PR fixes a subtle race condition in the retry logic and adds a regression test.",
        "files": [{"filename": "tests/test_retry.py"}],
        "additions": 20,
        "deletions": 5,
        "changed_files": 2,
    }
    result = calculate_reviewability(pr, security_findings=[], architecture_violations=[])
    assert result["score"] == 10


def test_undescribed_untested_massive_pr_scores_low():
    pr = {"description": "", "files": [], "additions": 2000, "deletions": 500, "changed_files": 40}
    result = calculate_reviewability(
        pr, security_findings=[{"name": "x"}], architecture_violations=[{"rule": "y"}]
    )
    assert result["score"] == 0


def test_score_is_capped_at_ten():
    pr = {"description": "x" * 50, "files": [{"filename": "tests/a.py"}], "additions": 1, "deletions": 1, "changed_files": 1}
    result = calculate_reviewability(pr, [], [])
    assert result["score"] <= 10
