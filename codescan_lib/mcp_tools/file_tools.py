"""
File-related MCP tools.

This module contains tools for working with files and their contents.
"""
from typing import Dict, Any, List

from .base import mcp, q, driver

@mcp.tool()
def list_files(random_string: str):
    """
    List all unique file paths present in the code graph.
    """
    query = """
    MATCH (f:File)
    RETURN f.path AS file, f.type AS type,
           CASE WHEN f:TestFile THEN true ELSE false END AS is_test_file,
           CASE WHEN f:ExampleFile THEN true ELSE false END AS is_example_file
    ORDER BY file
    """
    with driver.session() as session:
        results = session.run(query).data()
        return results

@mcp.tool()
def file_contents(file: str):
    """
    List all classes, functions, and constants contained in a specific file.

    Args:
        file: Path to the file to list contents from

    Returns:
        Dict with classes, functions, and constants in the file
    """
    query = """
    MATCH (f:File {path: $file})-[:CONTAINS]->(c:Class)
    RETURN c.name AS name, 'class' AS type, c.line AS line, c.end_line AS end_line
    UNION
    MATCH (f:File {path: $file})-[:CONTAINS]->(func:Function)
    RETURN func.name AS name, 'function' AS type, func.line AS line, func.end_line AS end_line
    UNION
    MATCH (f:File {path: $file})-[:CONTAINS]->(const:Constant)
    RETURN const.name AS name, 'constant' AS type, const.line AS line, const.end_line AS end_line
    ORDER BY line
    """
    with driver.session() as session:
        results = session.run(query, file=file).data()

        # Format the results for better display
        return {
            "file": file,
            "contents": results
        }

@mcp.tool()
def list_functions(file: str) -> List[Dict[str, Any]]:
    """
    List all functions defined in a specific file.

    Args:
        file: Path to the file to list functions from

    Returns:
        List of functions with their names and line numbers
    """
    return q("""
        MATCH (f:Function {file:$file})
        WHERE coalesce(f.is_reference,false)=false
        RETURN f.name AS name, f.line AS line, f.end_line AS end_line
        ORDER BY f.line
    """, file=file)

@mcp.tool()
def list_classes(file: str) -> List[Dict[str, Any]]:
    """
    List all classes defined in a specific file.

    Args:
        file: Path to the file to list classes from

    Returns:
        List of classes with their names and line numbers
    """
    return q("""
        MATCH (c:Class {file:$file})
        RETURN c.name AS class, c.line AS line, c.end_line AS end_line
        ORDER BY c.line
    """, file=file)
