"""Read the callee and the shape of a call from its AST node."""
import ast

from .call_targets import ATTR_CALL, BARE_CALL, SELF_CALL, SELF_NAMES
from .constants import BUILTIN_FUNCTIONS, CLASS_PRESERVING_DECORATORS


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


def keeps_class(decorators: list[ast.expr], trusted_imports: set[str]) -> bool:
    """True when every decorator is a known one (`@dataclass`, `@functools.total_ordering(...)`) imported from outside."""
    for decorator in decorators:
        target = decorator.func if isinstance(decorator, ast.Call) else decorator
        root = target
        while isinstance(root, ast.Attribute):
            root = root.value
        known = isinstance(root, ast.Name) and root.id in trusted_imports
        if not known or ast.unparse(target) not in CLASS_PRESERVING_DECORATORS:
            return False
    return True


def _deferred_roots(node: ast.AST) -> list[ast.expr | None]:
    if isinstance(node, ast.Lambda):
        return [node.body]
    if isinstance(node, ast.arg | ast.AnnAssign):
        return [node.annotation]
    if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
        return [node.returns]
    return []


def deferred_nodes(tree: ast.Module) -> set[int]:
    """ids of the nodes inside lambda bodies and annotations: code that runs later, or never, not at definition."""
    return {id(inner) for node in ast.walk(tree) for root in _deferred_roots(node) if root for inner in ast.walk(root)}
