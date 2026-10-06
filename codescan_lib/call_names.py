"""Read the callee and the shape of a call from its AST node."""
import ast

from .call_targets import ATTR_CALL, BARE_CALL, SELF_CALL, SELF_NAMES
from .constants import (
    BUILTIN_FUNCTIONS,
    CLASS_PRESERVING_DECORATORS,
    TYPE_CHECKING_MODULES,
    TYPE_CHECKING_NAME,
)


def callee_name(func: ast.expr, external_names: set[str]) -> str | None:
    """Name of the called function, or None for builtins and standard-library or third-party calls."""
    if isinstance(func, ast.Name):
        skipped = func.id in BUILTIN_FUNCTIONS or func.id in external_names
        return None if skipped else func.id
    if isinstance(func, ast.Attribute):
        root = func.value
        while isinstance(root, ast.Attribute):
            root = root.value
        if isinstance(root, ast.Name) and root.id in external_names:
            return None
        return func.attr
    return None


def call_site(node: ast.Call) -> str:
    """Where the call sits in the file, down to its columns: tells it from calls nested in it or around it."""
    return f"{node.lineno}:{node.col_offset}-{node.end_lineno}:{node.end_col_offset}"


def call_kind(func: ast.expr) -> str:
    """`name()` is bare, `self.name()` or `cls.name()` is a self call, anything else an attribute call."""
    if isinstance(func, ast.Name):
        return BARE_CALL
    receiver = func.value if isinstance(func, ast.Attribute) else None
    is_self = isinstance(receiver, ast.Name) and receiver.id in SELF_NAMES
    return SELF_CALL if is_self else ATTR_CALL


def _root(expr: ast.expr) -> ast.Name | None:
    while isinstance(expr, ast.Attribute):
        expr = expr.value
    return expr if isinstance(expr, ast.Name) and expr.id not in SELF_NAMES else None


def dotted_name(expr: ast.expr, imports: dict[str, str], blocked: set[str]) -> str:
    """Dotted name `expr` stands for, its first name resolved through the file's project imports.

    "" when it is unknown: the first name is `self`, `cls` or rebound in this function (`blocked`),
    or it is not an import and has attributes after it. A bare unimported name stands for itself
    (a class defined in this file).
    """
    root = _root(expr)
    if root is None or root.id in blocked:
        return ""
    chain: list[str] = []
    while isinstance(expr, ast.Attribute):
        chain.insert(0, expr.attr)
        expr = expr.value
    if root.id in imports:
        return ".".join([imports[root.id], *chain])
    return "" if chain else root.id


def receiver_hints(
    func: ast.expr, imports: dict[str, str], instances: dict[str, tuple[str, int]], blocked: set[str], line: int
) -> tuple[str, str]:
    """The class and the module an attribute call's receiver may be, "" for each that is unknown.

    `Foo.run()` and `x.run()` after `x = Foo()` name a class; `utils.run()` after `import pkg.utils as utils`
    names the class "pkg.utils" or the module "pkg.utils". A parameter, an attribute, a call result or a
    name the function rebinds names none. A bare `compute()` after
    `from pkg.a import compute` names the dotted name "pkg.a.compute" in the module slot. `instances` maps a name to its class and the line it was bound on.
    """
    if isinstance(func, ast.Name):
        return "", ("" if func.id in blocked else imports.get(func.id, ""))
    if not isinstance(func, ast.Attribute):
        return "", ""
    receiver = func.value
    if isinstance(receiver, ast.Name) and receiver.id in instances:
        built, bound_line = instances[receiver.id]
        return (built, "") if line > bound_line else ("", "")
    root = _root(receiver)
    name = dotted_name(receiver, imports, blocked)
    return name, name if root and root.id in imports else ""


def import_origins(tree: ast.Module) -> dict[str, str]:
    """Where each name this module imports comes from (`dc` -> `dataclasses.dataclass`); a name imported two ways has none."""
    origins: dict[str, str] = {}
    clashes: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            pairs = [(a.asname or a.name.split(".")[0], a.name if a.asname else a.name.split(".")[0]) for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            pairs = [(a.asname or a.name, f"{node.module}.{a.name}") for a in node.names]
        else:
            continue
        for name, origin in pairs:
            if origins.setdefault(name, origin) != origin:
                clashes.add(name)
    return {name: origin for name, origin in origins.items() if name not in clashes}


def keeps_class(decorators: list[ast.expr], trusted_imports: set[str], origins: dict[str, str]) -> bool:
    """True when every decorator is a known one, imported from the module that really defines it.

    `@dataclass` and `@dc` count after `from dataclasses import dataclass [as dc]`, `@dataclasses.dataclass(...)`
    after `import dataclasses`; the same name imported from anywhere else does not.
    """
    for decorator in decorators:
        target = decorator.func if isinstance(decorator, ast.Call) else decorator
        head, _, rest = ast.unparse(target).partition(".")
        origin = origins.get(head, "") if head in trusted_imports else ""
        if not origin or f"{origin}.{rest}".rstrip(".") not in CLASS_PRESERVING_DECORATORS:
            return False
    return True


def _deferred_roots(node: ast.AST) -> list[ast.expr | None]:
    """The parts of a node that run later or never: lambda bodies, annotations, generator bodies, type aliases."""
    if isinstance(node, ast.Lambda):
        return [node.body]
    if isinstance(node, ast.arg | ast.AnnAssign):
        return [node.annotation]
    if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
        return [node.returns]
    kind = type(node).__name__  # PEP 695 nodes (3.12) are matched by name: older `ast` modules lack them
    if kind == "TypeAlias":
        return [getattr(node, "value", None)]
    if kind == "TypeVar":
        return [getattr(node, "bound", None)]
    if isinstance(node, ast.GeneratorExp):  # only the first iterable is evaluated at once
        gens = node.generators
        return [node.elt, *(g.iter for g in gens[1:]), *(test for g in gens for test in g.ifs)]
    return []


def deferred_nodes(tree: ast.Module) -> set[int]:
    """ids of the nodes that run later, or never, rather than where they are written."""
    return {id(inner) for node in ast.walk(tree) for root in _deferred_roots(node) if root for inner in ast.walk(root)}


def is_type_checking(test: ast.expr, origins: dict[str, str], shadowed: set[str]) -> bool:
    """`TYPE_CHECKING` as imported from `typing` (or `typing_extensions`), alone or as one `and` operand.

    A name in `shadowed` (a parameter or assignment of the enclosing scope) is no longer the imported one.
    """
    if isinstance(test, ast.BoolOp) and isinstance(test.op, ast.And):
        return any(is_type_checking(value, origins, shadowed) for value in test.values)
    if isinstance(test, ast.Name):
        return test.id not in shadowed and origins.get(test.id, "") in {f"{m}.{TYPE_CHECKING_NAME}" for m in TYPE_CHECKING_MODULES}
    return (isinstance(test, ast.Attribute) and test.attr == TYPE_CHECKING_NAME
            and isinstance(test.value, ast.Name) and test.value.id not in shadowed
            and origins.get(test.value.id, "") in TYPE_CHECKING_MODULES)
