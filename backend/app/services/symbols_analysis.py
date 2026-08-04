import ast
import re
from typing import Dict, Any, List, Optional, Tuple


def _collect_definitions(source: str) -> Tuple[Dict[str, ast.AST], Dict[str, ast.AST]]:
    """Function/class defs anywhere in a parsed module, keyed by name (last
    definition wins on a duplicate name, same as the old regex's dedup)."""
    functions: Dict[str, ast.AST] = {}
    classes: Dict[str, ast.AST] = {}
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions[node.name] = node
        elif isinstance(node, ast.ClassDef):
            classes[node.name] = node
    return functions, classes


def _body_signature(node: ast.AST) -> str:
    # No line/col attributes, so a def that only moved (didn't change) isn't
    # flagged as modified.
    return ast.dump(node, include_attributes=False)


def extract_symbols_via_ast(base_source: Optional[str], head_source: str) -> Optional[Dict[str, List[str]]]:
    """
    Real AST diff between a file's state before and after the PR, using the
    actual file content (not a diff-hunk reconstruction). Returns None if
    either side fails to parse, signaling "fall back to regex on the patch".
    base_source is None for a brand-new file (nothing to diff against - the
    whole head file's defs are "added").
    """
    try:
        head_funcs, head_classes = _collect_definitions(head_source)
    except SyntaxError:
        return None

    if base_source is not None:
        try:
            base_funcs, base_classes = _collect_definitions(base_source)
        except SyntaxError:
            return None
    else:
        base_funcs, base_classes = {}, {}

    functions_added = [name for name in head_funcs if name not in base_funcs]
    functions_removed = [name for name in base_funcs if name not in head_funcs]
    functions_modified = [
        name for name in head_funcs
        if name in base_funcs and _body_signature(head_funcs[name]) != _body_signature(base_funcs[name])
    ]

    # classes_modified covers added/removed/changed classes alike - there's
    # no separate classes_added/classes_removed field in the response shape.
    classes_modified = [
        name for name in head_classes
        if name not in base_classes or _body_signature(head_classes[name]) != _body_signature(base_classes[name])
    ] + [name for name in base_classes if name not in head_classes]

    return {
        "functions_modified": functions_modified,
        "functions_added": functions_added,
        "functions_removed": functions_removed,
        "classes_modified": classes_modified,
    }


def extract_symbols_from_patch(patch: str, filename: str) -> Dict[str, List[str]]:
    # Fallback to regex for non-python or if AST parsing is skipped
    added_funcs = []
    removed_funcs = []
    mod_funcs = []
    mod_classes = []
    
    # Very basic regex heuristics for patches
    lines = patch.split('\n')
    current_context = None
    
    for line in lines:
        if line.startswith('@@'):
            # Extract context from @@ -... +... @@ context
            match = re.search(r'@@.*@@\s*(?:def|class|function)\s+([a-zA-Z0-9_]+)', line)
            if match:
                current_context = match.group(1)
                if line.find('class') != -1 and current_context not in mod_classes:
                    mod_classes.append(current_context)
                elif current_context not in mod_funcs:
                    mod_funcs.append(current_context)
                    
        elif line.startswith('+') and not line.startswith('+++'):
            # Detect added functions
            m = re.search(r'^\+\s*(?:def|async def|function|class)\s+([a-zA-Z0-9_]+)', line)
            if m:
                name = m.group(1)
                if "class" in line and name not in mod_classes:
                    mod_classes.append(name)
                elif name not in added_funcs:
                    added_funcs.append(name)
                    
        elif line.startswith('-') and not line.startswith('---'):
            m = re.search(r'^-\s*(?:def|async def|function|class)\s+([a-zA-Z0-9_]+)', line)
            if m:
                name = m.group(1)
                if "class" in line:
                    pass
                elif name not in removed_funcs:
                    removed_funcs.append(name)

    return {
        "functions_modified": mod_funcs,
        "functions_added": added_funcs,
        "functions_removed": removed_funcs,
        "classes_modified": mod_classes
    }

def analyze_symbols(pr_data: Dict[str, Any]) -> Dict[str, List[str]]:
    result = {
        "functions_modified": set(),
        "functions_added": set(),
        "functions_removed": set(),
        "classes_modified": set()
    }
    
    files = pr_data.get("files", [])

    for f in files:
        filename = f.get("filename", "")
        head_content = f.get("head_content")

        symbols = None
        if filename.endswith(".py") and head_content is not None:
            symbols = extract_symbols_via_ast(f.get("base_content"), head_content)

        if symbols is None:
            # No real content fetched for this file (non-Python, fetch
            # failed/skipped, or the head side didn't parse) - fall back to
            # regex heuristics on the diff patch.
            patch = f.get("patch", "")
            if not patch:
                continue
            symbols = extract_symbols_from_patch(patch, filename)

        for k in result.keys():
            result[k].update(symbols.get(k, []))
            
    # Convert sets to lists
    return {k: list(v) for k, v in result.items()}
