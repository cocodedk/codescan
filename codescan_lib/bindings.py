"""Count where a function binds each name, to tell which names a call receiver can be trusted for."""
import ast
from collections import Counter

from .call_names import is_type_checking


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
        """Count a name bound by an assignment, `for`, `with`, `del` or `:=` target."""
        if not isinstance(node.ctx, ast.Load):
            self.names[node.id] += 1

    def visit_arg(self, node: ast.arg) -> None:
        """Count a parameter as a binding."""
        self.names[node.arg] += 1

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        """`x: int` alone binds nothing."""
        if node.value is not None or not isinstance(node.target, ast.Name):
            self.visit(node.target)
        self.visit(node.annotation)
        if node.value is not None:
            self.visit(node.value)

    def visit_FunctionDef(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        """Count the function's name as bound here; its body is another scope."""
        self.names[node.name] += 1
        self.funcs[node.name] += 1
        defaults = [*node.args.defaults, *(d for d in node.args.kw_defaults if d)]
        for outer in (*node.decorator_list, *defaults):
            self.visit(outer)

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Count the class's name as bound here, and visit its body."""
        self.names[node.name] += 1
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import | ast.ImportFrom) -> None:
        """Count each name an import binds."""
        for alias in node.names:
            self.imports[alias.asname or alias.name.split(".")[0]] += 1

    visit_ImportFrom = visit_Import

    def visit_Global(self, node: ast.Global | ast.Nonlocal) -> None:
        """Count a `global` or `nonlocal` declaration as a binding of each name."""
        self.names.update(node.names)

    visit_Nonlocal = visit_Global

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        """Count the `as` name of an `except` clause."""
        if node.name:
            self.names[node.name] += 1
        self.generic_visit(node)

    def visit_MatchAs(self, node: ast.MatchAs | ast.MatchStar) -> None:
        """Count a `match` capture."""
        if node.name:
            self.names[node.name] += 1
        self.generic_visit(node)

    visit_MatchStar = visit_MatchAs

    def visit_MatchMapping(self, node: ast.MatchMapping) -> None:
        """Count the `**rest` capture of a mapping pattern."""
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
        """Count a module-level `def` as a definition."""
        self.defs[node.name] += 1
        super().visit_FunctionDef(node)

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        """Count a module-level `class` as a definition."""
        self.defs[node.name] += 1
        self.names[node.name] += 1
        for outer in (*node.decorator_list, *node.bases, *node.keywords):
            self.visit(outer)

    def sites(self, name: str) -> int:
        """Number of places the module binds `name`, imports included."""
        return self.names[name] + self.imports[name]

    def rebound(self) -> set[str]:
        """Names bound more than once, imports included: which binding a call sees is undecided."""
        return {name for name in self.names.keys() | self.imports.keys() if self.sites(name) > 1}

    def untrusted(self) -> set[str]:
        """Names no receiver or class call can rely on: bound more than once, by a function, or by any site
        that is no `def`, `class` or import (`A = Other`)."""
        return self.rebound() | {name for name in self.names if self.names[name] > self.defs[name]} | set(self.funcs)

    def unstable(self) -> set[str]:
        """Names a call to which may reach anything: bound by a site that is no `def`, `class` or import
        (even once), or bound more than once with a site that is no `def` or `class`."""
        return {name for name in self.names.keys() | self.imports.keys()
                if self.names[name] > self.defs[name] or (self.sites(name) > 1 and self.sites(name) > self.defs[name])}

    def bound_names(self) -> set[str]:
        """Every name the scan found a binding site for, imports included."""
        return set(self.names) | set(self.imports)

    def clean_exports(self) -> set[str]:
        """Names bound exactly once, by a `def` or `class`: what another module can import with certainty."""
        return {name for name in self.defs if self.sites(name) == 1}


def scan_module(tree: ast.Module) -> ModuleScan:
    """Count where the module binds each name in its own scope."""
    scan = ModuleScan()
    for statement in tree.body:
        scan.visit(statement)
    return scan


class RuntimeScan(ModuleScan):
    """A module scan that leaves out `if TYPE_CHECKING:` bodies: what they bind does not exist at runtime."""

    def __init__(self, origins: dict[str, str], shadowed: set[str]) -> None:
        super().__init__()
        self.origins = origins
        self.shadowed = shadowed

    def visit_If(self, node: ast.If) -> None:
        """Visit an `if`, leaving out the body of one guarded by `TYPE_CHECKING`."""
        if not is_type_checking(node.test, self.origins, self.shadowed):
            self.generic_visit(node)
            return
        for statement in node.orelse:
            self.visit(statement)


def runtime_bound_names(tree: ast.Module, origins: dict[str, str], shadowed: set[str]) -> set[str]:
    """Names the module binds when it runs."""
    scan = RuntimeScan(origins, shadowed)
    for statement in tree.body:
        scan.visit(statement)
    return scan.bound_names()
