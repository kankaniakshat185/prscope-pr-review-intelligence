from app.services.treesitter_engine import (
    collect_calls,
    extract_symbols_via_treesitter,
    is_supported_file,
)


def test_is_supported_file_recognizes_js_ts_extensions_only():
    assert is_supported_file("a.js")
    assert is_supported_file("a.jsx")
    assert is_supported_file("a.mjs")
    assert is_supported_file("a.cjs")
    assert is_supported_file("a.ts")
    assert is_supported_file("a.tsx")
    assert not is_supported_file("a.py")
    assert not is_supported_file("a.go")


# --- collect_calls ---


def test_collect_calls_from_a_named_function_declaration():
    source = "function helper() { return 1; }\nfunction main() { return helper(); }\n"
    assert collect_calls(source, "a.js") == [("main", "helper")]


def test_collect_calls_attributes_method_calls_by_property_name():
    source = "class Foo {\n  bar() { return this.baz(); }\n}\n"
    assert collect_calls(source, "a.js") == [("bar", "baz")]


def test_collect_calls_from_a_named_arrow_function():
    source = "const helper = () => 1;\nconst main = () => helper();\n"
    assert collect_calls(source, "a.ts") == [("main", "helper")]


def test_anonymous_callback_does_not_reset_the_enclosing_scope():
    # The inline arrow passed to forEach has no name of its own - both the
    # forEach() call and the helper() call inside it should still attribute
    # to "main", not to some anonymous/untracked scope.
    source = "function main() {\n  [1, 2].forEach(x => helper(x));\n}\n"
    assert collect_calls(source, "a.js") == [("main", "forEach"), ("main", "helper")]


def test_calls_at_module_scope_are_skipped():
    source = "function outside() {\n  doOutside();\n}\ndoTopLevel();\n"
    assert collect_calls(source, "a.js") == [("outside", "doOutside")]


def test_calling_the_result_of_another_call_has_no_static_callee_name_for_the_outer_call():
    # foo()() - the *outer* call's "function" field is itself a
    # call_expression (not an identifier/member_expression), so it
    # contributes no edge of its own. The inner foo() call is a distinct,
    # perfectly normal call and is still recorded.
    source = "function main() {\n  foo()();\n}\n"
    assert collect_calls(source, "a.js") == [("main", "foo")]


def test_unsupported_extension_returns_none():
    assert collect_calls("function f() {}", "a.py") is None


def test_tsx_file_parses_jsx_and_typescript_together():
    source = (
        "function helper() { return 1; }\n"
        "function Widget() {\n"
        "  return <div onClick={() => helper()}>{helper()}</div>;\n"
        "}\n"
    )
    calls = collect_calls(source, "a.tsx")
    assert ("Widget", "helper") in calls


# --- extract_symbols_via_treesitter ---


def test_symbols_detects_added_function():
    base = "function a() { return 1; }\n"
    head = "function a() { return 1; }\nfunction b() { return 2; }\n"
    result = extract_symbols_via_treesitter(base, head, "a.ts")
    assert result["functions_added"] == ["b"]
    assert result["functions_modified"] == []


def test_symbols_detects_removed_function():
    base = "function a() { return 1; }\nfunction b() { return 2; }\n"
    head = "function a() { return 1; }\n"
    result = extract_symbols_via_treesitter(base, head, "a.ts")
    assert result["functions_removed"] == ["b"]


def test_symbols_detects_modified_function_body():
    base = "function a() { return 1; }\n"
    head = "function a() { return 2; }\n"
    result = extract_symbols_via_treesitter(base, head, "a.ts")
    assert result["functions_modified"] == ["a"]


def test_symbols_ignores_a_function_that_only_moved():
    base = "function a() { return 1; }\nfunction b() { return 2; }\n"
    head = "function b() { return 2; }\nfunction a() { return 1; }\n"
    result = extract_symbols_via_treesitter(base, head, "a.ts")
    assert result == {"functions_modified": [], "functions_added": [], "functions_removed": [], "classes_modified": []}


def test_symbols_new_file_has_no_base_treats_everything_as_added():
    head = "function x() { return 1; }\n"
    result = extract_symbols_via_treesitter(None, head, "a.ts")
    assert result["functions_added"] == ["x"]


def test_symbols_detects_modified_class_and_its_method():
    base = "class C { m() { return 1; } }\n"
    head = "class C { m() { return 2; } }\n"
    result = extract_symbols_via_treesitter(base, head, "a.ts")
    assert result["classes_modified"] == ["C"]
    assert result["functions_modified"] == ["m"]


def test_symbols_detects_a_named_arrow_function_assigned_to_a_const():
    base = "const helper = () => 1;\n"
    head = "const helper = () => 1;\nconst other = () => 2;\n"
    result = extract_symbols_via_treesitter(base, head, "a.js")
    assert result["functions_added"] == ["other"]


def test_symbols_unsupported_extension_returns_none():
    assert extract_symbols_via_treesitter(None, "function f() {}", "a.py") is None
