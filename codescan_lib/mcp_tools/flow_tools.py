"""
Flow-analysis MCP tools.

This module contains tools that show where a codebase's flow can be simplified.
"""
from typing import Any

from .base import mcp, q


@mcp.tool()
def pass_through_functions() -> list[dict[str, Any]]:
    """
    List functions whose whole body is one call to another defined function (a layer that can usually be cut).

    A forwarder whose call CodeScan could not resolve to a defined function is not listed.
    `same_arguments` is true when the call passes exactly the forwarder's own parameters, in order, by name.
    `callers` counts the functions, and the files with module-level code, that call the forwarder.

    Returns:
        Rows of name, file, line, target, target_file, callers and same_arguments, most callers first.
    """
    return q(
        """
        MATCH (f:Function)-[:CALLS]->(t:Function)
        WHERE f.forwards_to IS NOT NULL AND f.is_reference = false AND NOT f:Test
          AND t.is_reference = false AND split(t.name, '.')[-1] = f.forwards_to
          AND NOT f.name ENDS WITH '__'
        WITH f, t ORDER BY t.file, t.line
        WITH f, head(collect(t)) AS target
        WITH f, target, COUNT { MATCH (caller)-[:CALLS]->(f) WHERE caller:Function OR caller:File } AS callers
        RETURN f.name AS name, f.file AS file, f.line AS line, target.name AS target,
               target.file AS target_file, callers, f.forwards_same_args AS same_arguments
        ORDER BY callers DESC, f.file, f.line
        """
    )
