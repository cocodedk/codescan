"""
Call graph lookup MCP tools: fan-in, fan-out, recursion, unresolved references and call arguments.
"""
from typing import Any

from .base import mcp, q


@mcp.tool()
def most_called_functions(limit: int = 10) -> list[dict[str, Any]]:
    """
    List functions with the most callers (fan-in).
    Args:
        limit: Maximum number of results to return (default 10)
    Returns:
        List of functions with their name, file, and number of callers.
    """
    return q(
        """
        MATCH (f:Function)
        WHERE coalesce(f.is_reference, false) = false
        OPTIONAL MATCH (caller:Function)-[:CALLS]->(f)
        WITH f, count(caller) AS num_callers
        ORDER BY num_callers DESC, f.file, f.line
        RETURN f.name AS name, f.file AS file, num_callers
        LIMIT $limit
        """,
        limit=limit
    )

@mcp.tool()
def most_calling_functions(limit: int = 10) -> list[dict[str, Any]]:
    """
    List functions that call the most other functions (fan-out).
    Args:
        limit: Maximum number of results to return (default 10)
    Returns:
        List of functions with their name, file, and number of callees.
    """
    return q(
        """
        MATCH (f:Function)
        WHERE coalesce(f.is_reference, false) = false
        OPTIONAL MATCH (f)-[:CALLS]->(callee:Function)
        WITH f, count(callee) AS num_callees
        ORDER BY num_callees DESC, f.file, f.line
        RETURN f.name AS name, f.file AS file, num_callees
        LIMIT $limit
        """,
        limit=limit
    )

@mcp.tool()
def recursive_functions() -> list[dict[str, Any]]:
    """
    List functions that call themselves (direct recursion).
    Returns:
        List of recursive functions with their name and file.
    """
    return q(
        """
        MATCH (f:Function)-[:CALLS]->(f2:Function)
        WHERE f = f2 AND coalesce(f.is_reference, false) = false
        RETURN f.name AS name, f.file AS file, f.line AS line
        ORDER BY f.file, f.line
        """
    )

@mcp.tool()
def functions_calling_references() -> list[dict[str, Any]]:
    """
    List functions that call at least one reference function (potential missing dependencies).
    Returns:
        List of function names, files, and the number of reference functions they call.
    """
    return q(
        """
        MATCH (f:Function)-[:CALLS]->(ref:Function:ReferenceFunction)
        WHERE coalesce(f.is_reference, false) = false
        WITH f, count(ref) AS num_reference_calls
        RETURN f.name AS name, f.file AS file, num_reference_calls
        ORDER BY num_reference_calls DESC, f.file, f.line
        """
    )

@mcp.tool()
def function_call_arguments(fn: str, file: str | None = None) -> list[dict[str, Any]]:
    """
    List all argument lists used in calls to a given function.
    Args:
        fn: Name of the function to inspect
        file: (Optional) File path to disambiguate overloaded or class methods
    Returns:
        List of argument lists, with caller name, caller file, and call site line number.
    """
    cypher = """
        MATCH (caller)-[call:CALLS]->(callee:Function {name:$fn})
        WHERE (caller:Function OR caller:File)"""
    if file:
        cypher += " AND callee.file = $file"
    cypher += """
        RETURN DISTINCT call.args AS args, coalesce(caller.name, caller.path) AS caller,
               coalesce(caller.file, caller.path) AS caller_file, call.line AS line
        ORDER BY line
    """
    params = {"fn": fn}
    if file:
        params["file"] = file
    return q(cypher, **params)
