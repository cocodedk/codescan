"""Count the paths through a function: its branch points, and how deeply its blocks nest."""
import ast
from collections.abc import Iterator

from .graph_batch import LINKS, GraphBatch

SET_COMPLEXITY = """UNWIND $rows AS row
    MATCH (f:Function {name: row.name, file: $file, line: row.line, is_reference: false})
    SET f.complexity = row.complexity, f.max_nesting = row.max_nesting"""
# Each of these adds one path (`and`/`or` and comprehension `if`s add one per extra operand / condition)
BRANCHES = (ast.If, ast.For, ast.AsyncFor, ast.While, ast.ExceptHandler, ast.match_case, ast.IfExp)
# Each of these opens a block one level deeper (`ast.TryStar`, the `except*` try, exists from 3.11)
BLOCKS = tuple(
    getattr(ast, name) for name in ("If", "For", "AsyncFor", "While", "Try", "TryStar", "With", "AsyncWith", "Match")
    if hasattr(ast, name)
)
DEFINITIONS = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)


def own_children(node: ast.AST) -> Iterator[ast.AST]:
    """Children of `node` that run as part of the function, leaving out the bodies of nested definitions."""
    if isinstance(node, ast.ClassDef):
        yield from (*node.decorator_list, *node.bases, *node.keywords)
    elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
        yield from (*node.decorator_list, node.args)
        if node.returns:
            yield node.returns
    else:
        yield from ast.iter_child_nodes(node)


def branch_points(node: ast.AST) -> int:
    """Number of extra paths this node adds to the function (0 for a node that is no branch)."""
    if isinstance(node, ast.BoolOp):
        return len(node.values) - 1
    if isinstance(node, ast.comprehension):
        return len(node.ifs)
    return int(isinstance(node, BRANCHES))


def measure(node: ast.AST, depth: int = 0, parent: ast.AST | None = None) -> tuple[int, int]:
    """(branch points, deepest block level) of `node` and everything inside it that belongs to the function."""
    # An `elif` is an `if` alone in the `else` of another, written at the same column: same level, not deeper
    is_elif = isinstance(node, ast.If) and isinstance(parent, ast.If) and node.col_offset == parent.col_offset
    inner = depth + 1 if isinstance(node, BLOCKS) and not is_elif else depth
    branches, deepest = branch_points(node), inner
    for child in own_children(node):
        child_branches, child_deepest = measure(child, inner, node)
        branches, deepest = branches + child_branches, max(deepest, child_deepest)
    return branches, deepest


def mark_complexity(batch: GraphBatch, node: ast.FunctionDef | ast.AsyncFunctionDef, name: str, line: int) -> None:
    """Queue `complexity` (1 + branch points) and `max_nesting` for a function's own body."""
    branches = deepest = 0
    for statement in node.body:
        found, level = measure(statement)
        branches, deepest = branches + found, max(deepest, level)
    batch.add(LINKS, SET_COMPLEXITY, name=name, line=line, complexity=1 + branches, max_nesting=deepest)
