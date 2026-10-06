"""Spot functions whose whole body is one call to another function."""
import ast

from .call_names import callee_name
from .graph_batch import LINKS, GraphBatch

SET_FORWARDER = """UNWIND $rows AS row
    MATCH (f:Function {name: row.name, file: $file, line: row.line, is_reference: false})
    SET f.forwards_to = row.forwards_to, f.forwards_same_args = row.same_args"""
SELF_PARAMETERS = 1  # a method's first parameter is the receiver, never passed on


def forwarded_call(node: ast.FunctionDef | ast.AsyncFunctionDef) -> ast.Call | None:
    """The call that is the function's whole body (after a docstring): `return <call>` or a bare `<call>`."""
    body = node.body
    if len(body) > 1 and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant):
        body = body[1:]
    if len(body) != 1 or not isinstance(body[0], ast.Return | ast.Expr):
        return None
    value = body[0].value
    value = value.value if isinstance(value, ast.Await) else value
    return value if isinstance(value, ast.Call) else None


def passed_on(node: ast.FunctionDef | ast.AsyncFunctionDef, call: ast.Call, is_method: bool) -> bool:
    """True when the call passes exactly the function's own parameters, in order, by name."""
    spec = node.args
    positional = [a.arg for a in [*spec.posonlyargs, *spec.args]][SELF_PARAMETERS if is_method else 0:]
    expected = [
        *positional,
        *([f"*{spec.vararg.arg}"] if spec.vararg else []),
        *(f"{a.arg}={a.arg}" for a in spec.kwonlyargs),
        *([f"**{spec.kwarg.arg}"] if spec.kwarg else []),
    ]
    return [ast.unparse(part) for part in [*call.args, *call.keywords]] == expected


def mark_forwarder(
    batch: GraphBatch, node: ast.FunctionDef | ast.AsyncFunctionDef, name: str, line: int,
    is_method: bool, external_names: set[str],
) -> None:
    """Queue `forwards_to` for a function that only passes a call on; any other function gets none."""
    call = forwarded_call(node)
    target = callee_name(call.func, external_names) if call else None
    if call and target:
        batch.add(LINKS, SET_FORWARDER, name=name, line=line, forwards_to=target,
                  same_args=passed_on(node, call, is_method))
