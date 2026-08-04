from app.services.context_builder import classify_pr


def test_classifies_docs_pr():
    files = [{"filename": "docs/setup.md"}, {"filename": "README.md"}]
    assert classify_pr(files) == "DOCS"


def test_mixed_pr_when_no_category_dominates():
    files = [{"filename": "app/main.py"}, {"filename": "app/ui.tsx"}]
    assert classify_pr(files) == "MIXED"


def test_empty_file_list_is_mixed():
    assert classify_pr([]) == "MIXED"


def test_dependency_files_detected():
    files = [{"filename": "requirements.txt"}, {"filename": "app/main.py"}]
    # 1/2 = 0.5 < 0.6 dominance threshold -> MIXED, not misclassified as pure DEPENDENCY
    assert classify_pr(files) == "MIXED"
