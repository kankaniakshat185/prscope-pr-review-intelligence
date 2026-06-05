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

def build_dependency_graph(files_changed: list, changed_symbols: dict) -> dict:
    """
    Build a call graph using AST and NetworkX.
    Extract calls and called_by for modified functions.
    """
    graph = nx.DiGraph()
    
    # We parse the full patch text or file content as a single script
    # to extract approximate calls. In a real system, we would fetch the raw files.
    # For this deterministic requirement, we will try to parse what we can.
    
    for f in files_changed:
        if not f.get("filename", "").endswith(".py"):
            continue
            
        patch = f.get("patch", "")
        # Very rough approximation: we extract all lines from the patch to form a script
        # This might not parse perfectly if it's just a diff, so we strip +/-
        lines = []
        for line in patch.split('\n'):
            if line.startswith('+') and not line.startswith('+++'):
                lines.append(line[1:])
            elif line.startswith(' ') or line.startswith('-'):
                # We include context and removed lines to maintain AST validity mostly
                lines.append(line[1:] if len(line) > 0 else "")
                
        source = "\n".join(lines)
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
