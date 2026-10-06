"""Count where a function binds each name, to tell which names a call receiver can be trusted for."""
import ast
from collections import Counter


class BindingScan(ast.NodeVisitor):
    """Counts the binding sites of one function's own scope, nested classes and comprehensions included.

    `names` counts every way of binding except imports (parameters, stores, `del`, `for`, `with`, `except`,
    `match` captures, `:=`, `global`, nested `def` and `class`); `imports` counts import statements.
    A nested function's name is bound here, but its parameters and body belong to its own scope.
    """

    def __init__(self) -> None:
        self.names: Counter[str] = Counter()
        self.imports: Counter[str] = Counter()

    def visit_Name(self, node: ast.Name) -> None:
        if not isinstance(node.ctx, ast.Load):
            self.names[node.id] += 1

    def visit_arg(self, node: ast.arg) -> None:
        self.names[node.arg] += 1

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        """`x: int` alone binds nothing."""
        if node.value is not None or not isinstance(node.target, ast.Name):
            self.visit(node.target)
        self.visit(node.annotation)
        if node.value is not None:
            self.visit(node.value)

    def visit_FunctionDef(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        self.names[node.name] += 1
        defaults = [*node.args.defaults, *(d for d in node.args.kw_defaults if d)]
        for outer in (*node.decorator_list, *defaults):
            self.visit(outer)

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.names[node.name] += 1
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import | ast.ImportFrom) -> None:
        for alias in node.names:
            self.imports[alias.asname or alias.name.split(".")[0]] += 1

    visit_ImportFrom = visit_Import

    def visit_Global(self, node: ast.Global | ast.Nonlocal) -> None:
        self.names.update(node.names)

    visit_Nonlocal = visit_Global

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        if node.name:
            self.names[node.name] += 1
        self.generic_visit(node)

    def visit_MatchAs(self, node: ast.MatchAs | ast.MatchStar) -> None:
        if node.name:
            self.names[node.name] += 1
        self.generic_visit(node)

    visit_MatchStar = visit_MatchAs

    def visit_MatchMapping(self, node: ast.MatchMapping) -> None:
        if node.rest:
            self.names[node.rest] += 1
        self.generic_visit(node)


def scan_function(node: ast.FunctionDef | ast.AsyncFunctionDef) -> BindingScan:
    """Binding sites in a function's parameters and body."""
    scan = BindingScan()
    scan.visit(node.args)
    for statement in node.body:
        scan.visit(statement)
    return scan


class ModuleScan(BindingScan):
    """Binding sites of a module's own scope: a class body binds only the class's name here."""

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.names[node.name] += 1


def rebound_in_module(tree: ast.Module) -> set[str]:
    """Names the module binds more than once, imports included: which binding a call sees is undecided."""
    scan = ModuleScan()
    for statement in tree.body:
        scan.visit(statement)
    return {name for name in scan.names.keys() | scan.imports.keys() if scan.names[name] + scan.imports[name] > 1}
