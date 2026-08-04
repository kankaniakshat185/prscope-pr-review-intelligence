"""
McCabe cyclomatic complexity via an actual control-flow graph (CFG), not
just an AST decision-point count.

Cyclomatic complexity of a single function is M = E - N + 2, where E is the
number of edges and N the number of nodes in the function's CFG (the "+2"
is "+2P" for a single connected component, P=1). This module builds that
graph explicitly - nodes and edges - rather than using the algebraically
equivalent shortcut of just counting `if`/`for`/`while`/`except`/boolean-
operator occurrences in the AST (which is what most complexity tools do
under the hood, since the two approaches always agree for structured code
with no unrestricted jumps). Building the real graph costs more code, but
means there's an actual object to reason about (and, potentially, render)
rather than a keyword tally.

Known, deliberate simplifications:
- `finally` blocks are treated as always executing after the try/except
  construct, not modeled as their own branch target.
- Nested function/lambda definitions are not descended into when computing
  the complexity of the enclosing function - each def is analyzed on its
  own when the walker reaches it separately.
- Same limitation as the rest of this codebase's diff-based analysis: this
  operates on a source string reconstructed from a diff patch, which is not
  always syntactically complete on its own.
"""

import ast
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class CFG:
    nodes: set = field(default_factory=set)
    edges: List[Tuple[str, str]] = field(default_factory=list)

    def complexity(self) -> int:
        # M = E - N + 2 for a single connected function CFG (P=1 component).
        return len(self.edges) - len(self.nodes) + 2


class _CFGBuilder:
    def __init__(self):
        self.cfg = CFG()
        self._counter = 0
        # stack of (continue_target, break_target) for the loop(s) we're inside
        self._loop_stack: List[Tuple[str, str]] = []
        self._exit_node: Optional[str] = None

    def _new_node(self) -> str:
        self._counter += 1
        node_id = f"n{self._counter}"
        self.cfg.nodes.add(node_id)
        return node_id

    def _connect(self, tails: List[str], node: str) -> None:
        for t in tails:
            self.cfg.edges.append((t, node))

    def _count_extra_decision_edges(self, expr: Optional[ast.AST]) -> int:
        """Boolean short-circuit operators and ternary expressions are each
        an additional implicit branch, not captured by walking statements
        alone. Counted directly as extra edges rather than extra nodes -
        equivalent effect on E - N + 2 as adding a tiny branch/join pair
        would have, without the bookkeeping overhead of doing so."""
        if expr is None:
            return 0
        count = 0
        for node in ast.walk(expr):
            if isinstance(node, ast.BoolOp):
                count += len(node.values) - 1  # e.g. "a and b and c" = 2 extra edges
            elif isinstance(node, ast.IfExp):
                count += 1
        return count

    def build_function(self, func_node) -> CFG:
        entry = self._new_node()
        # Created upfront so every early return/raise can route to the same
        # exit node, rather than each terminating statement creating its own
        # dead-end node that would inflate N without a matching edge.
        self._exit_node = self._new_node()
        tails = self._build_body(func_node.body, [entry])
        self._connect(tails, self._exit_node)  # normal fallthrough off the end of the function
        return self.cfg

    def _build_body(self, stmts: List[ast.stmt], tails: List[str]) -> List[str]:
        for stmt in stmts:
            tails = self._build_stmt(stmt, tails)
            if not tails:
                break  # unreachable code after a terminating statement (return/raise/break/continue)
        return tails

    def _build_stmt(self, stmt: ast.stmt, tails: List[str]) -> List[str]:
        if isinstance(stmt, ast.If):
            branch = self._new_node()
            self._connect(tails, branch)
            for _ in range(self._count_extra_decision_edges(stmt.test)):
                self.cfg.edges.append((branch, branch))  # implicit sub-branch within the condition itself

            then_tails = self._build_body(stmt.body, [branch])
            else_tails = self._build_body(stmt.orelse, [branch]) if stmt.orelse else [branch]
            return then_tails + else_tails

        if isinstance(stmt, (ast.For, ast.AsyncFor, ast.While)):
            header = self._new_node()
            self._connect(tails, header)
            exit_target = self._new_node()

            test_expr = getattr(stmt, "test", None)  # While has .test; For doesn't
            for _ in range(self._count_extra_decision_edges(test_expr)):
                self.cfg.edges.append((header, header))

            self._loop_stack.append((header, exit_target))
            body_tails = self._build_body(stmt.body, [header])
            self._connect(body_tails, header)  # back edge
            self._loop_stack.pop()

            self.cfg.edges.append((header, exit_target))  # loop-false / loop-exhausted edge
            if stmt.orelse:
                return self._build_body(stmt.orelse, [exit_target])
            return [exit_target]

        if isinstance(stmt, ast.Try):
            try_tails = self._build_body(stmt.body, tails)
            all_tails = list(try_tails)
            for handler in stmt.handlers:
                # Conservative approximation: any point in the try body could
                # raise, so the handler is reachable from the try entry.
                handler_tails = self._build_body(handler.body, list(tails))
                all_tails.extend(handler_tails)
            if stmt.orelse:
                all_tails = self._build_body(stmt.orelse, try_tails)
            if stmt.finalbody:
                return self._build_body(stmt.finalbody, all_tails)
            return all_tails

        if isinstance(stmt, (ast.Return, ast.Raise)):
            node = self._new_node()
            self._connect(tails, node)
            extra = self._count_extra_decision_edges(getattr(stmt, "value", None) or getattr(stmt, "exc", None))
            for _ in range(extra):
                self.cfg.edges.append((node, node))
            self.cfg.edges.append((node, self._exit_node))
            return []  # terminates this path - no fallthrough

        if isinstance(stmt, ast.Break):
            node = self._new_node()
            self._connect(tails, node)
            if self._loop_stack:
                self.cfg.edges.append((node, self._loop_stack[-1][1]))
            return []

        if isinstance(stmt, ast.Continue):
            node = self._new_node()
            self._connect(tails, node)
            if self._loop_stack:
                self.cfg.edges.append((node, self._loop_stack[-1][0]))
            return []

        # Any other simple statement (assignment, expression, with, etc.)
        node = self._new_node()
        self._connect(tails, node)
        for child_expr in ast.iter_child_nodes(stmt):
            if isinstance(child_expr, ast.expr):
                extra = self._count_extra_decision_edges(child_expr)
                for _ in range(extra):
                    self.cfg.edges.append((node, node))
        return [node]


def function_complexity(func_node) -> int:
    """Cyclomatic complexity of a single ast.FunctionDef/AsyncFunctionDef."""
    builder = _CFGBuilder()
    cfg = builder.build_function(func_node)
    return cfg.complexity()


def compute_function_complexities(patch: str) -> Dict[str, int]:
    """
    Reconstructs a Python file's added+context lines from a diff patch and
    computes cyclomatic complexity for every top-level function/method fully
    visible in that reconstruction. Returns {} if the fragment doesn't parse
    - same diff-fragment fragility as the rest of this codebase's AST-based
    analysis (architecture.py, dependency_engine.py).
    """
    lines = []
    for line in patch.split("\n"):
        if line.startswith("+") and not line.startswith("+++"):
            lines.append(line[1:])
        elif line.startswith(" "):
            lines.append(line[1:])
    source = "\n".join(lines)
    if not source.strip():
        return {}

    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {}

    results = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            try:
                results[node.name] = function_complexity(node)
            except Exception:
                continue  # a malformed/unusual construct shouldn't take down the whole analysis
    return results
