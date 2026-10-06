"""Decide which definitions a call can really reach, from the shape of the call."""
from collections.abc import Callable
from pathlib import Path
from typing import NamedTuple

BARE_CALL, SELF_CALL, ATTR_CALL = "bare", "self", "attr"
SELF_NAMES = ("self", "cls")
NOT_NESTED = -1  # parent_line of a definition that is not inside a function


class Definition(NamedTuple):
    name: str
    file: str
    line: int
    parent_line: int  # line of the function this one is defined in, or NOT_NESTED


Position = dict[tuple[str, int], Definition]


def is_method(d: Definition) -> bool:
    return "." in d.name


def module_of(file: str) -> str:
    """Dotted module name of a project file: `pkg/utils.py` and `pkg/utils/__init__.py` are `pkg.utils`."""
    parts = Path(file).with_suffix("").parts
    return ".".join(parts[:-1] if parts[-1:] == ("__init__",) else parts)


def narrowest(matches: list[Definition], tiers: list[Callable[[Definition], bool]]) -> list[Definition]:
    """The one definition of the first tier that has any, or nothing when that tier is ambiguous."""
    for tier in tiers:
        found = [d for d in matches if tier(d)]
        if found:
            return found if len(found) == 1 else []
    return []


def bare_targets(caller: Definition, candidates: list[Definition], by_position: Position) -> list[Definition]:
    """Functions a bare `name()` reaches: nested in the caller, in an enclosing function, then module level."""
    functions = [d for d in candidates if not is_method(d)]
    scope: Definition | None = caller
    while scope:
        nested = [d for d in functions if d.file == caller.file and d.parent_line == scope.line]
        if nested:
            return nested if len(nested) == 1 else []
        scope = by_position.get((caller.file, scope.parent_line))
    module_level = [d for d in functions if d.parent_line == NOT_NESTED]
    same_file = [d for d in module_level if d.file == caller.file]
    return same_file or (module_level if len({d.file for d in module_level}) == 1 else [])


def self_targets(caller: Definition, callee: str, candidates: list[Definition]) -> list[Definition]:
    """Methods `self.name()` reaches: the caller's own class first, then the closest file."""
    owner = caller.name.rpartition(".")[0]
    methods = [d for d in candidates if is_method(d)]
    own = lambda d: bool(owner) and d.name == f"{owner}.{callee}" and d.file == caller.file
    return narrowest(methods, [own, lambda d: d.file == caller.file, lambda d: True])


def receiver_targets(
    caller: Definition, callee: str, candidates: list[Definition], recv_class: str, recv_module: str
) -> list[Definition]:
    """Definitions `receiver.name()` reaches when the receiver is a known project class or module.

    A class named through its module (`models.Runner`) counts only if it is defined in that module.
    """
    class_module, _, class_name = recv_class.rpartition(".")
    methods = [d for d in candidates if d.name == f"{class_name}.{callee}"]
    if class_module:
        methods = [d for d in methods if module_of(d.file) == class_module]
        tiers = [lambda d: True]
    else:
        tiers = [lambda d: d.file == caller.file, lambda d: True]
    if methods:
        return narrowest(methods, tiers)
    if not recv_module:
        return []
    return [d for d in candidates if not is_method(d) and d.parent_line == NOT_NESTED and module_of(d.file) == recv_module]


def choose_targets(
    caller: Definition, callee: str, candidates: list[Definition], by_position: Position,
    kind: str = ATTR_CALL, recv_class: str = "", recv_module: str = "",
) -> list[Definition]:
    """Every definition a call certainly refers to; an empty list leaves the call unresolved."""
    if kind == BARE_CALL:
        return bare_targets(caller, candidates, by_position)
    if kind == SELF_CALL:
        return self_targets(caller, callee, candidates)
    return receiver_targets(caller, callee, candidates, recv_class, recv_module)
