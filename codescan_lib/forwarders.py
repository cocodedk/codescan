"""Spot functions whose whole body is one call to another function."""
import ast

from .call_names import call_site, callee_name
from .graph_batch import LINKS, GraphBatch

SET_FORWARDER = """UNWIND $rows AS row
    MATCH (f:Function {name: row.name, file: $file, line: row.line, is_reference: false})
    SET f.forwards_to = row.forwards_to, f.forwards_site = row.site,
        f.forwards_same_args = row.same_args"""
SELF_PARAMETERS = 1  # a method's first parameter is the receiver, never passed on


def is_docstring(value: ast.expr) -> bool:
    return isinstance(value, ast.Constant) and isinstance(value.value, str)


def is_static(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    """`@staticmethod`, however it is spelled (`@builtins.staticmethod`)."""
    return any(ast.unparse(d).rpartition(".")[2] == "staticmethod" for d in node.decorator_list)


def forwarded_call(node: ast.FunctionDef | ast.AsyncFunctionDef) -> ast.Call | None:
    """The call that is the function's whole body (after a docstring): `return <call>` or a bare `<call>`."""
    body = node.body
    if len(body) > 1 and isinstance(body[0], ast.Expr) and is_docstring(body[0].value):
        body = body[1:]
    if len(body) != 1 or not isinstance(body[0], ast.Return | ast.Expr):
        return None
    value = body[0].value
    value = value.value if isinstance(value, ast.Await) else value
    return value if isinstance(value, ast.Call) else None


def passed_on(node: ast.FunctionDef | ast.AsyncFunctionDef, call: ast.Call, is_method: bool) -> bool:
    """True when the call passes every parameter of the function once, unchanged, and nothing else.

    A parameter goes positionally (in order) or as a keyword with its own name; `*args` and `**kwargs` as themselves.
    """
    spec = node.args
    positional = [a.arg for a in [*spec.posonlyargs, *spec.args]][SELF_PARAMETERS if is_method else 0:]
    expected = [
        *positional, *(a.arg for a in spec.kwonlyargs),
        *([f"*{spec.vararg.arg}"] if spec.vararg else []), *([f"**{spec.kwarg.arg}"] if spec.kwarg else []),
    ]
    passed: list[str] = []
    for index, arg in enumerate(call.args):
        if isinstance(arg, ast.Starred) and isinstance(arg.value, ast.Name):
            passed.append(f"*{arg.value.id}")
        elif isinstance(arg, ast.Name) and index < len(positional) and arg.id == positional[index]:
            passed.append(arg.id)
        else:
            return False
    for keyword in call.keywords:
        if not isinstance(keyword.value, ast.Name):
            return False
        passed.append(f"**{keyword.value.id}" if keyword.arg is None else keyword.arg)
        if keyword.arg is not None and keyword.value.id != keyword.arg:
            return False
    return sorted(passed) == sorted(expected)


def mark_forwarder(
    batch: GraphBatch, node: ast.FunctionDef | ast.AsyncFunctionDef, name: str, line: int,
    is_method: bool, external_names: set[str],
) -> None:
    """Queue `forwards_to` for a function that only passes a call on; any other function gets none."""
    call = forwarded_call(node)
    target = callee_name(call.func, external_names) if call else None
    if call and target:
        batch.add(LINKS, SET_FORWARDER, name=name, line=line, forwards_to=target,
                  site=call_site(call),
                  same_args=passed_on(node, call, is_method and not is_static(node)))
