from app.services.symbols_analysis import analyze_symbols, extract_symbols_via_ast


def test_detects_added_function():
    pr_data = {
        "files": [
            {
                "filename": "app/utils.py",
                "patch": "@@ -1,2 +1,5 @@\n import os\n+def new_helper():\n+    pass\n",
            }
        ]
    }
    result = analyze_symbols(pr_data)
    assert "new_helper" in result["functions_added"]


def test_detects_removed_function():
    pr_data = {
        "files": [
            {
                "filename": "app/utils.py",
                "patch": "@@ -1,3 +1,1 @@\n import os\n-def old_helper():\n-    pass\n",
            }
        ]
    }
    result = analyze_symbols(pr_data)
    assert "old_helper" in result["functions_removed"]


def test_no_patch_does_not_crash():
    pr_data = {"files": [{"filename": "app/binary.png", "patch": ""}]}
    result = analyze_symbols(pr_data)
    assert result == {
        "functions_modified": [],
        "functions_added": [],
        "functions_removed": [],
        "classes_modified": [],
    }


# --- extract_symbols_via_ast: real base/head content diffing ---


def test_ast_diff_detects_added_function():
    base = "def a():\n    return 1\n"
    head = "def a():\n    return 1\n\ndef b():\n    return 2\n"
    result = extract_symbols_via_ast(base, head)
    assert result["functions_added"] == ["b"]
    assert result["functions_modified"] == []
    assert result["functions_removed"] == []


def test_ast_diff_detects_removed_function():
    base = "def a():\n    return 1\n\ndef b():\n    return 2\n"
    head = "def a():\n    return 1\n"
    result = extract_symbols_via_ast(base, head)
    assert result["functions_removed"] == ["b"]
    assert result["functions_added"] == []


def test_ast_diff_detects_modified_function_body():
    base = "def a():\n    return 1\n"
    head = "def a():\n    return 2\n"
    result = extract_symbols_via_ast(base, head)
    assert result["functions_modified"] == ["a"]
    assert result["functions_added"] == []
    assert result["functions_removed"] == []


def test_ast_diff_ignores_a_function_that_only_moved():
    # This is the real win over regex-on-patch: a function that's byte-for-
    # byte identical but relocated in the file isn't falsely flagged.
    base = "def a():\n    return 1\n\ndef b():\n    return 2\n"
    head = "def b():\n    return 2\n\ndef a():\n    return 1\n"
    result = extract_symbols_via_ast(base, head)
    assert result["functions_modified"] == []
    assert result["functions_added"] == []
    assert result["functions_removed"] == []


def test_ast_diff_new_file_has_no_base_treats_everything_as_added():
    head = "def x():\n    pass\n"
    result = extract_symbols_via_ast(None, head)
    assert result["functions_added"] == ["x"]


def test_ast_diff_detects_modified_class_and_its_method():
    base = "class C:\n    def m(self):\n        return 1\n"
    head = "class C:\n    def m(self):\n        return 2\n"
    result = extract_symbols_via_ast(base, head)
    assert result["classes_modified"] == ["C"]
    assert result["functions_modified"] == ["m"]


def test_ast_diff_returns_none_when_head_does_not_parse():
    result = extract_symbols_via_ast("def a(): pass", "def a( this is not valid python")
    assert result is None


def test_ast_diff_returns_none_when_base_does_not_parse():
    result = extract_symbols_via_ast("def a( not valid", "def a():\n    pass\n")
    assert result is None


# --- analyze_symbols: routes to AST diff when real content is available,
# falls back to patch regex otherwise ---


def test_analyze_symbols_prefers_real_content_over_patch_when_both_present():
    # The patch text alone would suggest "helper" was added; the real
    # base/head content proves it only moved - AST diff should win.
    pr_data = {
        "files": [
            {
                "filename": "app/utils.py",
                "patch": "@@ -1,2 +1,2 @@\n+def helper():\n+    return 1\n",
                "base_content": "def helper():\n    return 1\n\ndef other():\n    pass\n",
                "head_content": "def other():\n    pass\n\ndef helper():\n    return 1\n",
            }
        ]
    }
    result = analyze_symbols(pr_data)
    assert result["functions_added"] == []
    assert result["functions_modified"] == []


def test_analyze_symbols_falls_back_to_patch_when_no_head_content():
    pr_data = {
        "files": [
            {
                "filename": "app/utils.py",
                "patch": "@@ -1,2 +1,5 @@\n import os\n+def new_helper():\n+    pass\n",
                "base_content": None,
                "head_content": None,
            }
        ]
    }
    result = analyze_symbols(pr_data)
    assert "new_helper" in result["functions_added"]
