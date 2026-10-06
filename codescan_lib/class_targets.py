"""Decide which project class a call such as `Foo()` or `models.Foo()` certainly builds."""
from typing import NamedTuple

from .call_targets import ATTR_CALL, BARE_CALL, Exporters


class ClassDefinition(NamedTuple):
    name: str
    file: str
    line: int
    nested: bool  # defined inside a function or another class: no other file can name it bare
    plain: bool  # no decorator that could replace it: a call to the name builds this class


def is_certain(c: ClassDefinition) -> bool:
    return c.plain and not c.nested


def exported_classes(
    callee: str, candidates: list[ClassDefinition], module: str, exporters: Exporters
) -> list[ClassDefinition]:
    """The class `callee` of a module, only if the module binds that name once and the file defines one such class."""
    file, exports = exporters.get(module, ("", set()))
    in_file = [c for c in candidates if c.file == file]
    return in_file if callee in exports and len(in_file) == 1 and is_certain(in_file[0]) else []


def bare_classes(caller_file: str, candidates: list[ClassDefinition]) -> list[ClassDefinition]:
    """Classes a bare, unimported `Foo()` reaches: the one in the caller's file, else the only one anywhere."""
    same_file = [c for c in candidates if c.file == caller_file]
    if same_file:
        return same_file if len(same_file) == 1 and is_certain(same_file[0]) else []
    anywhere = [c for c in candidates if not c.nested]
    return anywhere if len(anywhere) == 1 and anywhere[0].plain else []


def class_targets(
    caller_file: str, callee: str, candidates: list[ClassDefinition], kind: str, recv_module: str,
    exporters: Exporters,
) -> list[ClassDefinition]:
    """Every class a call certainly builds, under the same rules as a function call; empty when unsure.

    `recv_module` is the dotted name an imported callee or a module receiver stands for (see receiver_hints).
    """
    if kind == BARE_CALL and recv_module:  # `from pkg.a import Foo`; a name imported `as` another resolves to nothing
        module, _, name = recv_module.rpartition(".")
        return exported_classes(callee, candidates, module, exporters) if name == callee else []
    if kind == BARE_CALL:
        return bare_classes(caller_file, candidates)
    if kind == ATTR_CALL and recv_module:
        return exported_classes(callee, candidates, recv_module, exporters)
    return []
