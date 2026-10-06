"""Decide which definitions a call can really reach, from the shape of the call."""
from collections.abc import Callable
from pathlib import Path
from typing import NamedTuple

from .constants import ATTR_CALL, BARE_CALL, SELF_CALL

NOT_NESTED = -1  # parent_line of a definition that is not inside a function


class Definition(NamedTuple):
    """A function or method defined in the project: where it is and which function it is nested in."""

    name: str
    file: str
    line: int
    parent_line: int  # line of the function this one is defined in, or NOT_NESTED


Position = dict[tuple[str, int], Definition]


def module_scope(file: str) -> Definition:
    """Stand-in caller for code outside every function: it sees what module level sees, and has no `self`."""
    return Definition("", file, 0, NOT_NESTED)


def is_method(d: Definition) -> bool:
    """True when the definition is a method (its name has a class prefix)."""
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


Exporters = dict[str, tuple[str, set[str]]]  # module -> (the file that is the module, names it binds once by a def)


def build_exporters(files: list[tuple[str, list[str]]]) -> Exporters:
    """Which file a module name means: the package when `pkg/a/__init__.py` and `pkg/a.py` both exist."""
    exporters: Exporters = {}
    for path, exports in sorted(files, key=lambda f: Path(f[0]).name != "__init__.py"):
        exporters.setdefault(module_of(path), (path, set(exports)))
    return exporters


def exported_functions(callee: str, candidates: list[Definition], module: str, exporters: Exporters) -> list[Definition]:
    """Module-level function `callee` of a module, only if the module binds that name once, by a `def`."""
    file, exports = exporters.get(module, ("", set()))
    if callee not in exports:
        return []
    return [d for d in candidates if d.file == file and not is_method(d) and d.parent_line == NOT_NESTED]


def imported_targets(callee: str, candidates: list[Definition], imported: str, exporters: Exporters) -> list[Definition]:
    """Functions a bare name reaches when the file imported it as `imported` (`pkg.a.compute`).

    A name imported under another name (`as`) resolves to nothing.
    """
    module, _, name = imported.rpartition(".")
    return exported_functions(callee, candidates, module, exporters) if name == callee else []


def self_targets(caller: Definition, callee: str, candidates: list[Definition]) -> list[Definition]:
    """Methods `self.name()` reaches: the caller's own class first, then the closest file. None at module level."""
    if not caller.name:
        return []
    owner = caller.name.rpartition(".")[0]
    methods = [d for d in candidates if is_method(d)]
    own = lambda d: bool(owner) and d.name == f"{owner}.{callee}" and d.file == caller.file
    return narrowest(methods, [own, lambda d: d.file == caller.file, lambda d: True])


def receiver_targets(
    caller: Definition, callee: str, candidates: list[Definition], recv_class: str, recv_module: str,
    exporters: Exporters,
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
    return exported_functions(callee, candidates, recv_module, exporters)


def choose_targets(
    caller: Definition, callee: str, candidates: list[Definition], by_position: Position,
    kind: str = ATTR_CALL, recv_class: str = "", recv_module: str = "", exporters: Exporters | None = None,
) -> list[Definition]:
    """Every definition a call certainly refers to; an empty list leaves the call unresolved."""
    if kind == BARE_CALL and recv_module:
        return imported_targets(callee, candidates, recv_module, exporters or {})
    if kind == BARE_CALL:
        return bare_targets(caller, candidates, by_position)
    if kind == SELF_CALL:
        return self_targets(caller, callee, candidates)
    return receiver_targets(caller, callee, candidates, recv_class, recv_module, exporters or {})
