"""
Test-coverage MCP tools.

This module contains tools that tell which code the tests exercise and which they do not.
"""
from typing import Any

from .base import mcp, q


@mcp.tool()
def untested_functions(exclude_private: bool = True) -> list[dict[str, Any]]:
    """
    List defined functions that no test is known to exercise.

    A test links to a function only through a certain call, its name or its class, so a method a
    test calls through a parameter or fixture (`runner.run()`) shows up here even if it is tested.
    `possible_tests` counts unresolved calls from tests that use the same name: above 0, the
    function may well be tested. Treat every row as a lead to check, not proof.

    Args:
        exclude_private: Whether to exclude private functions (starting with _)

    Returns:
        Rows of name, file, line and possible_tests.
    """
    where_clause = "WHERE NOT f:TestFunction AND f.is_reference = false AND NOT (:TestFunction)-[:TESTS]->(f)"

    if exclude_private:
        where_clause += " AND NOT f.name STARTS WITH '_'"

    return q(f"""
        MATCH (f:Function)
        {where_clause}
        OPTIONAL MATCH (:TestFunction)-[r:CALLS]->(:ReferenceFunction {{name: split(f.name, '.')[-1]}})
        WITH f, count(r) AS possible_tests
        RETURN f.name AS name, f.file AS file, f.line AS line, possible_tests
        ORDER BY f.file, f.line
    """)

@mcp.tool()
def get_test_coverage_ratio() -> list[dict[str, Any]]:
    """
    Get the share of defined functions that some test is known to exercise.

    A lower bound: tests that reach a function only through a parameter or fixture are not
    counted (see untested_functions and its possible_tests column).

    Returns:
        Overall test coverage ratio and counts
    """
    return q("""
        MATCH (f:Function) WHERE NOT f:TestFunction AND f.is_reference = false
        WITH count(f) AS total_functions
        MATCH (f:Function) WHERE NOT f:TestFunction AND f.is_reference = false
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
