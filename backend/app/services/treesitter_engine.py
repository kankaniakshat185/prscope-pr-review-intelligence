from typing import Dict, List, Optional, Tuple

import tree_sitter_javascript as tsjs
import tree_sitter_typescript as tsts
from tree_sitter import Language, Node, Parser

_JS_LANGUAGE = Language(tsjs.language())
_TS_LANGUAGE = Language(tsts.language_typescript())
_TSX_LANGUAGE = Language(tsts.language_tsx())

# tree-sitter-javascript's grammar already parses JSX without error (JSX is
# part of the same grammar), so plain .js/.jsx share one language; .tsx gets
# its own grammar variant for TS-flavored JSX.
_EXTENSION_LANGUAGES: Dict[str, Language] = {
    ".js": _JS_LANGUAGE,
    ".jsx": _JS_LANGUAGE,
    ".mjs": _JS_LANGUAGE,
    ".cjs": _JS_LANGUAGE,
    ".ts": _TS_LANGUAGE,
    ".tsx": _TSX_LANGUAGE,
}

# Node types that introduce a "named function scope" for call-graph
# attribution purposes - the equivalent of Python ast.FunctionDef/
# AsyncFunctionDef. function_expression/arrow_function only count when
# they're bound to a name (const x = () => ...); anonymous ones (inline
# callbacks) don't reset the current scope, same as how the Python
# CallGraphVisitor never special-cases lambdas.
_NAMED_DECL_TYPES = {"function_declaration", "generator_function_declaration", "method_definition"}
_NAMED_VALUE_TYPES = {"function_expression", "generator_function", "arrow_function"}


def is_supported_file(filename: str) -> bool:
    return any(filename.endswith(ext) for ext in _EXTENSION_LANGUAGES)


def _language_for(filename: str) -> Optional[Language]:
    for ext, language in _EXTENSION_LANGUAGES.items():
        if filename.endswith(ext):
            return language
    return None


def _parse(source: str, filename: str) -> Optional[Node]:
    language = _language_for(filename)
    if language is None:
        return None
    parser = Parser(language)
    tree = parser.parse(source.encode("utf-8", errors="replace"))
    return tree.root_node


def _text(node: Optional[Node]) -> Optional[str]:
    return node.text.decode("utf-8", errors="replace") if node is not None else None


def collect_definitions(source: str, filename: str) -> Optional[Tuple[Dict[str, Node], Dict[str, Node]]]:
    """
    Function/class-like defs anywhere in the file, keyed by name - the
    tree-sitter analogue of symbols_analysis._collect_definitions. Includes
    named function/arrow expressions bound via `const x = () => {...}`
    (keyed by the variable name), not just `function x() {}` declarations
    and class methods. Returns None if this filename's extension has no
    grammar registered.
    """
    root = _parse(source, filename)
    if root is None:
        return None

    functions: Dict[str, Node] = {}
    classes: Dict[str, Node] = {}

    def walk(node: Node) -> None:
        if node.type in _NAMED_DECL_TYPES:
            name = _text(node.child_by_field_name("name"))
            if name:
                functions[name] = node
        elif node.type == "class_declaration":
            name = _text(node.child_by_field_name("name"))
            if name:
                classes[name] = node
        elif node.type == "variable_declarator":
            value = node.child_by_field_name("value")
            if value is not None and value.type in _NAMED_VALUE_TYPES:
                name_node = node.child_by_field_name("name")
                if name_node is not None and name_node.type == "identifier":
                    functions[_text(name_node)] = value

        for child in node.children:
            walk(child)

    walk(root)
    return functions, classes


def extract_symbols_via_treesitter(
    base_source: Optional[str], head_source: str, filename: str
) -> Optional[Dict[str, List[str]]]:
    """
    Real diff between a JS/TS file's state before and after the PR, using
    the actual file content - the tree-sitter analogue of
    symbols_analysis.extract_symbols_via_ast. "Modified" is exact source
    text equality of the def's node, not a structural AST comparison (no
    ast.dump() equivalent here) - simpler, and still means a def that only
    *moved* without changing isn't falsely flagged, same as the Python path.
    """
    head_defs = collect_definitions(head_source, filename)
    if head_defs is None:
        return None
    head_funcs, head_classes = head_defs

    if base_source is not None:
        base_defs = collect_definitions(base_source, filename)
        if base_defs is None:
            return None
        base_funcs, base_classes = base_defs
    else:
        base_funcs, base_classes = {}, {}

    functions_added = [name for name in head_funcs if name not in base_funcs]
    functions_removed = [name for name in base_funcs if name not in head_funcs]
    functions_modified = [
        name for name in head_funcs
        if name in base_funcs and head_funcs[name].text != base_funcs[name].text
    ]

    classes_modified = [
        name for name in head_classes
        if name not in base_classes or head_classes[name].text != base_classes[name].text
    ] + [name for name in base_classes if name not in head_classes]

    return {
        "functions_modified": functions_modified,
        "functions_added": functions_added,
        "functions_removed": functions_removed,
        "classes_modified": classes_modified,
    }


def _enclosing_scope_name(node: Node) -> Optional[str]:
    if node.type in _NAMED_DECL_TYPES:
        return _text(node.child_by_field_name("name"))
    if node.type in _NAMED_VALUE_TYPES:
        parent = node.parent
        if parent is not None and parent.type == "variable_declarator":
            name_node = parent.child_by_field_name("name")
            if name_node is not None and name_node.type == "identifier":
                return _text(name_node)
        return None  # anonymous - caller keeps attributing to the enclosing named scope
    return None


def _callee_name(call_node: Node) -> Optional[str]:
    fn = call_node.child_by_field_name("function")
    if fn is None:
        return None
    if fn.type == "identifier":
        return _text(fn)
    if fn.type == "member_expression":
        return _text(fn.child_by_field_name("property"))
    return None  # e.g. calling the result of another call: foo()()


def collect_calls(source: str, filename: str) -> Optional[List[Tuple[str, str]]]:
    """
    (caller, callee) pairs for every call expression inside a named
    function/method/arrow scope - the tree-sitter analogue of
    dependency_engine.CallGraphVisitor. Calls at module scope (no enclosing
    named function) are skipped, same as the Python visitor.
    """
    root = _parse(source, filename)
    if root is None:
        return None

    calls: List[Tuple[str, str]] = []

    def walk(node: Node, current: Optional[str]) -> None:
        next_current = current
        if node.type in _NAMED_DECL_TYPES or node.type in _NAMED_VALUE_TYPES:
            name = _enclosing_scope_name(node)
            if name:
                next_current = name

        if node.type == "call_expression" and current:
            callee = _callee_name(node)
            if callee:
                calls.append((current, callee))

        for child in node.children:
            walk(child, next_current)

    walk(root, None)
    return calls
