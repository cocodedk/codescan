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
        self.funcs: Counter[str] = Counter()  # the `def` statements among the `names` sites

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
        self.funcs[node.name] += 1
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
    """Binding sites of a module's own scope: a class body binds only the class's name here.

    Decorators, bases, defaults and comprehensions count (a walrus in them binds in the module);
    `defs` counts the `def` and `class` statements among the sites.
    """

    def __init__(self) -> None:
        super().__init__()
        self.defs: Counter[str] = Counter()

    def visit_FunctionDef(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        self.defs[node.name] += 1
        super().visit_FunctionDef(node)

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.defs[node.name] += 1
        self.names[node.name] += 1
        for outer in (*node.decorator_list, *node.bases, *node.keywords):
            self.visit(outer)

    def sites(self, name: str) -> int:
        return self.names[name] + self.imports[name]

    def rebound(self) -> set[str]:
        """Names bound more than once, imports included: which binding a call sees is undecided."""
        return {name for name in self.names.keys() | self.imports.keys() if self.sites(name) > 1}

    def untrusted(self) -> set[str]:
        """Names no receiver or class call can rely on: bound more than once, by a function, or by any site
        that is no `def`, `class` or import (`A = Other`)."""
        return self.rebound() | {name for name in self.names if self.names[name] > self.defs[name]} | set(self.funcs)

    def unstable(self) -> set[str]:
        """Names bound more than once with a site that is no `def` or `class`: a call to one may reach anything."""
        return {name for name in self.names.keys() | self.imports.keys()
                if self.sites(name) > 1 and self.sites(name) > self.defs[name]}

    def clean_exports(self) -> set[str]:
        """Names bound exactly once, by a `def` or `class`: what another module can import with certainty."""
        return {name for name in self.defs if self.sites(name) == 1}


def scan_module(tree: ast.Module) -> ModuleScan:
    scan = ModuleScan()
    for statement in tree.body:
        scan.visit(statement)
    return scan
