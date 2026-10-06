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
    `callers` counts the functions that call the forwarder; module-level code does not count.

    Returns:
        Rows of name, file, line, target, target_file, callers and same_arguments, most callers first.
    """
    return q(
        """
        MATCH (f:Function)-[r:CALLS]->(t:Function)
        WHERE r.line = f.forwards_line AND r.args = f.forwards_args AND f.forwards_to IS NOT NULL AND f.is_reference = false AND NOT f:Test
          AND t.is_reference = false AND split(t.name, '.')[-1] = f.forwards_to
          AND NOT (split(f.name, '.')[-1] STARTS WITH '__' AND f.name ENDS WITH '__')
        WITH f, t ORDER BY t.file, t.line
        WITH f, head(collect(t)) AS target
        WITH f, target, COUNT { MATCH (caller:Function)-[:CALLS]->(f) RETURN DISTINCT caller } AS callers
        RETURN f.name AS name, f.file AS file, f.line AS line, target.name AS target,
               target.file AS target_file, callers, f.forwards_same_args AS same_arguments
        ORDER BY callers DESC, f.file, f.line
        """
    )
