"""
Call graph analysis MCP tools.

This module contains tools for analyzing the call graph.
"""
from typing import Any

from .base import mcp, q


@mcp.tool()
def callees(fn: str) -> list[dict[str, Any]]:
    """
    Find functions called by a specific function.

    Args:
        fn: Name of the function to find callees for

    Returns:
        List of functions called by the specified function
    """
    return q("""
        MATCH (caller:Function {name:$fn})-[:CALLS]->(callee:Function)
        RETURN callee.name AS callee, caller.file AS caller_file
    """, fn=fn)

@mcp.tool()
def callers(fn: str) -> list[dict[str, Any]]:
    """
    Find functions that call a specific function.

    Args:
        fn: Name of the function called by others

    Returns:
        List of functions that call the specified function
    """
    return q("""
        MATCH (caller:Function)-[:CALLS]->(callee:Function {name:$fn})
        RETURN caller.name AS caller, caller.file AS caller_file
    """, fn=fn)

@mcp.tool()
def unresolved_references() -> list[dict[str, Any]]:
    """
    List unresolved function references in the codebase.

    Returns:
        List of unresolved function references and where they were first seen
    """
    return q("""
        MATCH (f:Function:ReferenceFunction)
        RETURN f.name AS name, f.file AS first_seen_in
    """)

@mcp.tool()
def uncalled_functions() -> list[dict[str, Any]]:
    """
    List all user-defined functions that are not called by any other function.

    Returns:
        List of functions (name, file, line, end_line) that have no incoming CALLS relationships.
    """
    return q(
        """
        MATCH (f:Function)
        WHERE coalesce(f.is_reference, false) = false
          AND NOT (():Function)-[:CALLS]->(f)
        RETURN f.name AS name, f.file AS file, f.line AS line, f.end_line AS end_line
        ORDER BY f.file, f.line
        """
    )

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
        MATCH (caller:Function)-[call:CALLS]->(callee:Function {name:$fn})
        """
    if file:
        cypher += " WHERE callee.file = $file"
    cypher += """
        RETURN DISTINCT call.args AS args, caller.name AS caller, caller.file AS caller_file, call.line AS line
        ORDER BY line
    """
    params = {"fn": fn}
    if file:
        params["file"] = file
    return q(cypher, **params)

@mcp.tool()
def transitive_calls(source_fn: str, target_fn: str, max_depth: int = 10) -> list[dict[str, Any]]:
    """
    Find full relationship chains between two functions (if one call will eventually lead to the other).

    Args:
        source_fn: Name of the source function
        target_fn: Name of the target function
        max_depth: Maximum path length to consider (default: 10)

    Returns:
        List of paths showing how source_fn eventually calls target_fn
    """
    # Cypher's variable-length relationship bound (*1..N) must be a literal in
    # the query text -- Neo4j does not allow binding it as a query parameter.
    # int() guards against pasting an unexpected value into the query.
    return q(f"""
        MATCH path = (source:Function {{name: $source_fn}})-[:CALLS*1..{int(max_depth)}]->(target:Function {{name: $target_fn}})
        WHERE length(path) <= $max_depth
        WITH path, [node IN nodes(path) | node.name] AS function_names
        RETURN
            function_names,
            length(path) AS path_length,
            [node IN nodes(path) | node.file] AS function_files
        ORDER BY path_length
        LIMIT 10
    """, source_fn=source_fn, target_fn=target_fn, max_depth=max_depth)

@mcp.tool()
def find_function_relations(function_name: str, partial_match: bool = False, limit: int = 50) -> dict[str, Any]:
    """
    Find function relations by function name, with option to search by partial name.

    Args:
        function_name: Full or partial name of the function to find relations for
        partial_match: If True, will match functions containing the specified name substring
        limit: Maximum number of results to return (default: 50)

    Returns:
        Dictionary with matching functions, their callers, and callees
    """
    # First find matching functions
    if partial_match:
        matching_functions = q("""
            MATCH (f:Function)
            WHERE f.name CONTAINS $name
            RETURN f.name AS name, f.file AS file, f.line AS line, f.end_line AS end_line
            ORDER BY f.file, f.line
            LIMIT $limit
        """, name=function_name, limit=limit)
    else:
        matching_functions = q("""
            MATCH (f:Function {name: $name})
            RETURN f.name AS name, f.file AS file, f.line AS line, f.end_line AS end_line
            ORDER BY f.file, f.line
            LIMIT $limit
        """, name=function_name, limit=limit)

    # If no functions found, return early
    if not matching_functions:
        return {
            "matching_functions": [],
            "relations": []
        }

    # For each matching function, find its callers and callees
    relations = []
    for fn in matching_functions:
        # Get callers
        callers_result = q("""
            MATCH (caller:Function)-[:CALLS]->(f:Function {name: $name})
            WHERE f.file = $file
            RETURN caller.name AS caller_name, caller.file AS caller_file
            LIMIT $limit
        """, name=fn["name"], file=fn["file"], limit=limit)

        # Get callees
        callees_result = q("""
            MATCH (f:Function {name: $name})-[:CALLS]->(callee:Function)
            WHERE f.file = $file
            RETURN callee.name AS callee_name, callee.file AS callee_file
            LIMIT $limit
        """, name=fn["name"], file=fn["file"], limit=limit)

        relations.append({
            "function": fn,
            "callers": callers_result,
            "callees": callees_result
        })

    return {
        "matching_functions": matching_functions,
        "relations": relations
    }
