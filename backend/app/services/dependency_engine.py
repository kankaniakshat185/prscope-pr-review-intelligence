import ast
import networkx as nx

class CallGraphVisitor(ast.NodeVisitor):
    def __init__(self):
        self.current_function = None
        self.calls = []

    def visit_FunctionDef(self, node):
        old_function = self.current_function
        self.current_function = node.name
        self.generic_visit(node)
        self.current_function = old_function

    def visit_AsyncFunctionDef(self, node):
        self.visit_FunctionDef(node)

    def visit_Call(self, node):
        if self.current_function:
            if isinstance(node.func, ast.Name):
                self.calls.append((self.current_function, node.func.id))
            elif isinstance(node.func, ast.Attribute):
                self.calls.append((self.current_function, node.func.attr))
        self.generic_visit(node)

def _reconstruct_source_from_patch(patch: str) -> str:
    """
    Fallback used only when we don't have the real head file content (fetch
    failed/skipped for this file): stitch the diff hunk's context/added/
    removed lines back into something parse-able. Inherently lossy - a diff
    hunk is a fragment, not a full file - kept only as a fallback, not the
    primary path.
    """
    lines = []
    for line in patch.split('\n'):
        if line.startswith('+') and not line.startswith('+++'):
            lines.append(line[1:])
        elif line.startswith(' ') or line.startswith('-'):
            lines.append(line[1:] if len(line) > 0 else "")
    return "\n".join(lines)


def build_dependency_graph(files_changed: list, changed_symbols: dict) -> dict:
    """
    Build a call graph using AST and NetworkX.
    Extract calls and called_by for modified functions.
    """
    graph = nx.DiGraph()

    for f in files_changed:
        if not f.get("filename", "").endswith(".py"):
            continue

        # Prefer the real head file content fetched from GitHub - parsing
        # the whole file (not just the diff hunk) means calls made from/to
        # untouched parts of the same file are captured accurately too.
        # Cross-file calls are still out of scope (that needs a full-repo
        # index, not a per-PR fetch).
        source = f.get("head_content")
        if source is None:
            source = _reconstruct_source_from_patch(f.get("patch", ""))

        try:
            tree = ast.parse(source)
            visitor = CallGraphVisitor()
            visitor.visit(tree)

            for caller, callee in visitor.calls:
                graph.add_edge(caller, callee)
        except SyntaxError:
            pass
            
    dependencies = []
    
    # Now for the modified functions, get their blast radius
    for func in changed_symbols.get("functions_modified", []) + changed_symbols.get("functions_added", []):
        calls = []
        called_by = []
        
        if graph.has_node(func):
            calls = list(graph.successors(func))
            called_by = list(graph.predecessors(func))
            
        dependencies.append({
            "function": func,
            "calls": calls,
            "called_by": called_by
        })
        
    return {
        "modified_functions": dependencies,
        "total_edges": graph.number_of_edges()
    }
