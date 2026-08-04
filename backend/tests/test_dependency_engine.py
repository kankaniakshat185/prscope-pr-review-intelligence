from app.services.dependency_engine import build_dependency_graph


def test_uses_real_head_content_when_available():
    head = "def helper():\n    return 1\n\ndef main():\n    return helper()\n"
    files_changed = [{"filename": "app/utils.py", "patch": "", "head_content": head}]
    changed_symbols = {"functions_modified": ["main"], "functions_added": []}

    result = build_dependency_graph(files_changed, changed_symbols)

    assert result["total_edges"] == 1
    main_entry = next(f for f in result["modified_functions"] if f["function"] == "main")
    assert main_entry["calls"] == ["helper"]
    assert main_entry["called_by"] == []


def test_falls_back_to_patch_reconstruction_when_no_head_content():
    patch = "@@ -1,2 +1,2 @@\n+def target():\n+    return 1\n"
    files_changed = [{"filename": "app/utils.py", "patch": patch, "head_content": None}]
    changed_symbols = {"functions_modified": ["target"], "functions_added": []}

    result = build_dependency_graph(files_changed, changed_symbols)

    target_entry = next(f for f in result["modified_functions"] if f["function"] == "target")
    assert target_entry["calls"] == []
    assert target_entry["called_by"] == []


def test_real_content_captures_calls_from_untouched_code_that_diff_reconstruction_would_miss():
    # unrelated_caller is untouched by the diff (only "target" changed), so
    # it never appears in the patch hunk at all - diff-fragment reconstruction
    # has no way to know it calls target. Real head content does.
    head = (
        "def unrelated_caller():\n"
        "    return target()\n"
        "\n"
        "def target():\n"
        "    return 99\n"
    )
    patch = "@@ -4,2 +4,2 @@\n-def target():\n-    return 1\n+def target():\n+    return 99\n"
    changed_symbols = {"functions_modified": ["target"], "functions_added": []}

    with_real_content = build_dependency_graph(
        [{"filename": "app/svc.py", "patch": patch, "head_content": head}], changed_symbols
    )
    without_real_content = build_dependency_graph(
        [{"filename": "app/svc.py", "patch": patch, "head_content": None}], changed_symbols
    )

    target_with = next(f for f in with_real_content["modified_functions"] if f["function"] == "target")
    target_without = next(f for f in without_real_content["modified_functions"] if f["function"] == "target")

    assert target_with["called_by"] == ["unrelated_caller"]
    assert target_without["called_by"] == []


def test_files_in_a_language_with_no_grammar_are_skipped_entirely():
    files_changed = [{"filename": "app/main.go", "patch": "", "head_content": "func main() { helper() }"}]
    changed_symbols = {"functions_modified": ["main"], "functions_added": []}

    result = build_dependency_graph(files_changed, changed_symbols)

    assert result["total_edges"] == 0
    main_entry = next(f for f in result["modified_functions"] if f["function"] == "main")
    assert main_entry["calls"] == []
    assert main_entry["called_by"] == []


def test_js_file_with_real_head_content_produces_call_graph_edges():
    head = "function helper() { return 1; }\nfunction main() { return helper(); }\n"
    files_changed = [{"filename": "app/index.js", "patch": "", "head_content": head}]
    changed_symbols = {"functions_modified": ["main"], "functions_added": []}

    result = build_dependency_graph(files_changed, changed_symbols)

    assert result["total_edges"] == 1
    main_entry = next(f for f in result["modified_functions"] if f["function"] == "main")
    assert main_entry["calls"] == ["helper"]


def test_js_file_without_head_content_is_skipped_no_diff_fragment_fallback():
    files_changed = [{"filename": "app/index.js", "patch": "+function main() { helper(); }", "head_content": None}]
    changed_symbols = {"functions_modified": ["main"], "functions_added": []}

    result = build_dependency_graph(files_changed, changed_symbols)

    assert result["total_edges"] == 0


def test_unparseable_head_content_does_not_crash():
    files_changed = [{"filename": "app/broken.py", "patch": "", "head_content": "def broken( not valid python"}]
    changed_symbols = {"functions_modified": [], "functions_added": []}

    result = build_dependency_graph(files_changed, changed_symbols)

    assert result == {"modified_functions": [], "total_edges": 0}
