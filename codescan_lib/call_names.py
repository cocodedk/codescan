"""Read the callee and the shape of a call from its AST node."""
import ast

from .constants import BUILTIN_FUNCTIONS
from .relationships import ATTR_CALL, BARE_CALL, SELF_CALL


def callee_name(func: ast.expr, stdlib_names: set[str]) -> str | None:
    """Name of the called function, or None for builtins and standard-library calls."""
    if isinstance(func, ast.Name):
        skipped = func.id in BUILTIN_FUNCTIONS or func.id in stdlib_names
        return None if skipped else func.id
    if isinstance(func, ast.Attribute):
        root = func.value
        while isinstance(root, ast.Attribute):
            root = root.value
        if isinstance(root, ast.Name) and root.id in stdlib_names:
            return None
        return func.attr
    return None


def call_kind(func: ast.expr) -> str:
    """`name()` is bare, `self.name()` or `cls.name()` is a self call, anything else an attribute call."""
    if isinstance(func, ast.Name):
        return BARE_CALL
    receiver = func.value if isinstance(func, ast.Attribute) else None
    is_self = isinstance(receiver, ast.Name) and receiver.id in ("self", "cls")
    return SELF_CALL if is_self else ATTR_CALL
