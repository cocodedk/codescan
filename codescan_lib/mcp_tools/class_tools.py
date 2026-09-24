"""
Class-related MCP tools.

This module contains tools for working with classes.
"""
from typing import Any

from .base import mcp, q


@mcp.tool()
def classes_with_no_methods() -> list[dict[str, Any]]:
    """
    List classes that do not contain any methods.
    Returns:
        List of class names and files with no outgoing CONTAINS relationships.
    """
    return q(
        """
        MATCH (c:Class)
        WHERE NOT (c)-[:CONTAINS]->(:Function)
        RETURN c.name AS class, c.file AS file, c.line AS line
        ORDER BY c.file, c.line
        """
    )

@mcp.tool()
def classes_with_most_methods(limit: int = 10) -> list[dict[str, Any]]:
    """
    List classes with the most methods.
    Args:
        limit: Maximum number of results to return (default 10)
    Returns:
        List of class names, files, and method counts.
    """
    return q(
        """
        MATCH (c:Class)
        OPTIONAL MATCH (c)-[:CONTAINS]->(f:Function)
        WITH c, count(f) AS num_methods
        ORDER BY num_methods DESC, c.file, c.line
        RETURN c.name AS class, c.file AS file, num_methods
        LIMIT $limit
        """,
        limit=limit
    )

@mcp.tool()
def find_class_relations(class_name: str, partial_match: bool = False, limit: int = 50) -> dict[str, Any]:
    """
    Find class relations by class name, with option to search by partial name.

    Args:
        class_name: Full or partial name of the class to find relations for
        partial_match: If True, will match classes containing the specified name substring
        limit: Maximum number of results to return (default: 50)

    Returns:
        Dictionary with matching classes, their methods, and containing files
    """
    # First find matching classes
    if partial_match:
        matching_classes = q("""
            MATCH (c:Class)
            WHERE c.name CONTAINS $name
            RETURN c.name AS name, c.file AS file, c.line AS line, c.end_line AS end_line
            ORDER BY c.file, c.line
            LIMIT $limit
        """, name=class_name, limit=limit)
    else:
        matching_classes = q("""
            MATCH (c:Class {name: $name})
            RETURN c.name AS name, c.file AS file, c.line AS line, c.end_line AS end_line
            ORDER BY c.file, c.line
            LIMIT $limit
        """, name=class_name, limit=limit)

    # If no classes found, return early
    if not matching_classes:
        return {
            "matching_classes": [],
            "relations": []
        }

    # For each matching class, find its methods and containing file
    relations = []
    for cls in matching_classes:
        # Get methods in the class
        methods_result = q("""
            MATCH (c:Class {name: $name, file: $file})-[:CONTAINS]->(f:Function)
            RETURN f.name AS method_name, f.line AS method_line, f.end_line AS method_end_line, f.length AS method_length
            ORDER BY f.line
            LIMIT $limit
        """, name=cls["name"], file=cls["file"], limit=limit)

        # Get containing file details
        file_result = q("""
            MATCH (f:File)-[:CONTAINS]->(c:Class {name: $name, file: $file})
            RETURN f.path AS file_path, f.type AS file_type, f.is_test AS is_test_file, f.is_example AS is_example_file
            LIMIT 1
        """, name=cls["name"], file=cls["file"])

        # Get classes that contain similar method names (potential related classes)
        related_classes = q("""
            MATCH (c:Class {name: $name, file: $file})-[:CONTAINS]->(f:Function)
            WITH collect(f.name) AS method_names
            MATCH (other:Class)-[:CONTAINS]->(of:Function)
            WHERE other.name <> $name AND of.name IN method_names
            WITH other, count(of) AS shared_methods
            ORDER BY shared_methods DESC
            RETURN other.name AS related_class_name, other.file AS related_class_file, shared_methods
            LIMIT $limit
        """, name=cls["name"], file=cls["file"], limit=limit)

        relations.append({
            "class": cls,
            "methods": methods_result,
            "file": file_result[0] if file_result else None,
            "related_classes": related_classes
        })

    return {
        "matching_classes": matching_classes,
        "relations": relations
    }
