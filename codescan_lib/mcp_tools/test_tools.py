"""
Test-related MCP tools.

This module contains tools for working with tests and test coverage.
"""
from typing import Any

from .base import mcp, q


@mcp.tool()
def list_test_functions() -> list[dict[str, Any]]:
    """
    List all test functions.

    Returns:
        List of test functions with their names, files, and line numbers
    """
    return q("""
        MATCH (f:TestFunction)
        RETURN f.name AS name, f.file AS file, f.line AS line, f.end_line AS end_line
        ORDER BY f.file, f.line
    """)

@mcp.tool()
def list_example_functions() -> list[dict[str, Any]]:
    """
    List all example functions.

    Returns:
        List of example functions with their names, files, and line numbers
    """
    return q("""
        MATCH (f:ExampleFunction)
        RETURN f.name AS name, f.file AS file, f.line AS line, f.end_line AS end_line
        ORDER BY f.file, f.line
    """)

@mcp.tool()
def list_test_classes() -> list[dict[str, Any]]:
    """
    List all test classes.

    Returns:
        List of test classes with their names, files, and line numbers
    """
    return q("""
        MATCH (c:TestClass)
        RETURN c.name AS name, c.file AS file, c.line AS line, c.end_line AS end_line
        ORDER BY c.file, c.line
    """)

@mcp.tool()
def list_example_classes() -> list[dict[str, Any]]:
    """
    List all example classes.

    Returns:
        List of example classes with their names, files, and line numbers
    """
    return q("""
        MATCH (c:ExampleClass)
        RETURN c.name AS name, c.file AS file, c.line AS line, c.end_line AS end_line
        ORDER BY c.file, c.line
    """)

@mcp.tool()
def get_test_files() -> list[dict[str, str]]:
    """
    List all files containing tests.

    Returns:
        List of file paths containing test components
    """
    return q("""
        MATCH (n:Test)
        RETURN DISTINCT n.file AS file
        ORDER BY file
    """)

@mcp.tool()
def get_example_files() -> list[dict[str, str]]:
    """
    List all files containing examples.

    Returns:
        List of file paths containing example components
    """
    return q("""
        MATCH (n:Example)
        RETURN DISTINCT n.file AS file
        ORDER BY file
    """)

@mcp.tool()
def get_test_detection_config() -> dict[str, list[str]]:
    """
    Get the current test detection configuration.

    Returns:
        Dictionary with test detection pattern configuration
    """
    # Import the config from codescan_lib
    from codescan_lib.constants import (
        TEST_CLASS_PATTERNS,
        TEST_DIR_PATTERNS,
        TEST_FILE_PATTERNS,
        TEST_FUNCTION_PREFIXES,
    )

    return {
        "test_dir_patterns": TEST_DIR_PATTERNS,
        "test_file_patterns": TEST_FILE_PATTERNS,
        "test_function_prefixes": TEST_FUNCTION_PREFIXES,
        "test_class_patterns": TEST_CLASS_PATTERNS
    }

@mcp.tool()
def untested_functions(exclude_private: bool = True) -> list[dict[str, Any]]:
    """
    List functions without tests.

    Args:
        exclude_private: Whether to exclude private functions (starting with _)

    Returns:
        List of functions that don't have any tests covering them
    """
    where_clause = "WHERE NOT f:TestFunction AND NOT (:TestFunction)-[:TESTS]->(f)"

    if exclude_private:
        where_clause += " AND NOT f.name STARTS WITH '_'"

    return q(f"""
        MATCH (f:Function)
        {where_clause}
        RETURN f.name AS name, f.file AS file, f.line AS line
        ORDER BY f.file, f.line
    """)

@mcp.tool()
def get_test_coverage_ratio() -> list[dict[str, Any]]:
    """
    Get test coverage ratio.

    Returns:
        Overall test coverage ratio and counts
    """
    return q("""
        MATCH (f:Function) WHERE NOT f:TestFunction
        WITH count(f) AS total_functions
        MATCH (f:Function) WHERE NOT f:TestFunction
          AND (:TestFunction)-[:TESTS]->(f)
        WITH total_functions, count(f) AS tested_functions
        RETURN
            total_functions,
            tested_functions,
            CASE
                WHEN total_functions > 0 THEN toFloat(tested_functions) / total_functions
                ELSE 0
            END AS coverage_ratio
    """)

@mcp.tool()
def functions_tested_by(file: str) -> list[dict[str, Any]]:
    """
    List functions tested by a specific test file.

    Args:
        file: Path to the test file

    Returns:
        List of functions tested by the specified test file
    """
    return q("""
        MATCH (test:TestFunction {file: $file})-[r:TESTS]->(f:Function)
        RETURN f.name AS tested_name, f.file AS tested_file, r.method AS method
        ORDER BY f.file, f.line
    """, file=file)

@mcp.tool()
def get_tests_for_function(name: str, file: str | None = None) -> list[dict[str, Any]]:
    """
    List tests for a specific function.

    Args:
        name: Name of the function
        file: Optional file path to disambiguate functions with the same name

    Returns:
        List of test functions that test the specified function
    """
    query = """
        MATCH (test:TestFunction)-[r:TESTS]->(f:Function {name: $name})
    """
    params = {"name": name}

    if file:
        query += " WHERE f.file = $file"
        params["file"] = file

    query += """
        RETURN test.name AS test_name, test.file AS test_file, r.method AS method
        ORDER BY test.file, test.line
    """

    return q(query, **params)

@mcp.tool()
def untested_classes(exclude_private: bool = True) -> list[dict[str, Any]]:
    """
    List classes without tests.

    Args:
        exclude_private: Whether to exclude private classes (starting with _)

    Returns:
        List of classes that don't have any tests covering them
    """
    where_clause = "WHERE NOT c:TestClass AND NOT (:TestClass)-[:TESTS]->(c)"

    if exclude_private:
        where_clause += " AND NOT c.name STARTS WITH '_'"

    return q(f"""
        MATCH (c:Class)
        {where_clause}
        RETURN c.name AS name, c.file AS file, c.line AS line
        ORDER BY c.file, c.line
    """)
