"""Turn the right-hand side of a constant assignment into a readable value and type."""
import ast

_CONTAINER_TYPES: dict[type[ast.expr], str] = {
    ast.List: "list",
    ast.Dict: "dict",
    ast.Tuple: "tuple",
    ast.Set: "set",
}
EXPRESSION_TYPE = "expression"


def extract_constant_value(node: ast.expr | None) -> tuple[str, str]:
    """Return (source text, type name) for a constant's value node."""
    if node is None:
        return "None", "NoneType"
    if isinstance(node, ast.Constant):
        return repr(node.value), type(node.value).__name__
    if (
        isinstance(node, ast.UnaryOp)
        and isinstance(node.op, (ast.USub, ast.UAdd))
        and isinstance(node.operand, ast.Constant)
    ):
        return ast.unparse(node), type(node.operand.value).__name__
    return ast.unparse(node), _CONTAINER_TYPES.get(type(node), EXPRESSION_TYPE)
