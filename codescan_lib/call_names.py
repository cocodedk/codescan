"""Read the callee and the shape of a call from its AST node."""
import ast

from .call_targets import ATTR_CALL, BARE_CALL, SELF_CALL, SELF_NAMES
from .constants import BUILTIN_FUNCTIONS


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


def receiver_hint(func: ast.expr, imports: dict[str, str], instances: dict[str, str]) -> str:
    """Dotted name of the class or module an attribute call's receiver may be, or "" when it is unknown.

    `Foo.run()` gives "Foo", `x.run()` after `x = Foo()` gives "Foo", and `utils.run()` after
    `import pkg.utils as utils` gives "pkg.utils". A parameter, an attribute or a call result gives "".
    """
    if not isinstance(func, ast.Attribute):
        return ""
    parts: list[str] = []
    receiver = func.value
    while isinstance(receiver, ast.Attribute):
        parts.insert(0, receiver.attr)
        receiver = receiver.value
    if not isinstance(receiver, ast.Name) or receiver.id in SELF_NAMES:
        return ""
    if receiver.id in instances:
        return "" if parts else instances[receiver.id]
    if receiver.id in imports:
        return ".".join([imports[receiver.id], *parts])
    return "" if parts else receiver.id
