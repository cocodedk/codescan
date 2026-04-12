"""
Constant-related MCP tools.

This module contains tools for working with constants.
"""

from .base import mcp, get_db_session

@mcp.tool()
def repetitive_constants(limit: int = 10) -> list:
    """
    List constants with identical values used in multiple places across the codebase.

    Args:
        limit: Maximum number of results to return (default 10)

    Returns:
        List of constants with the same value used in multiple places,
        showing value, type, and locations where they are defined.
    """
    with get_db_session() as session:
        # Find constants with the same value used in multiple places
        result = session.run("""
            MATCH (c1:Constant)
            WITH c1.value AS value, collect(c1) AS constants
            WHERE size(constants) > 1
            RETURN
                value,
                [c in constants | c.type][0] AS type,
                size(constants) AS count,
                [c in constants | {
                    name: c.name,
                    file: c.file,
                    line: c.line,
                    scope: c.scope
                }] AS occurrences
            ORDER BY count DESC
            LIMIT $limit
        """, limit=limit).data()

        return result

@mcp.tool()
def repetitive_constant_names(limit: int = 10) -> list:
    """
    Find constants with the same name used in multiple places across the codebase,
    regardless of their values.

    Args:
        limit: Maximum number of results to return (default 10)

    Returns:
        List of constant names used in multiple places,
        showing the locations and values where they are defined.
    """
    with get_db_session() as session:
        # Find constants with the same name used in multiple places
        result = session.run("""
            MATCH (c1:Constant)
            WITH c1.name AS name, collect(c1) AS constants
            WHERE size(constants) > 1
            RETURN
                name,
                size(constants) AS count,
                [c in constants | {
                    value: c.value,
                    type: c.type,
                    file: c.file,
                    line: c.line,
                    scope: c.scope
                }] AS occurrences
            ORDER BY count DESC
            LIMIT $limit
        """, limit=limit).data()

        return result
