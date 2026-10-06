"""
Test-related MCP tools.

This module contains tools for listing tests and examples and the test detection configuration.
"""
from typing import Any

from .base import mcp, q


def _defined(var: str, label: str) -> list[dict[str, Any]]:
    """Nodes with `label` (a class or function kind) with where each is defined, by file and line."""
    return q(f"""
        MATCH ({var}:{label})
        RETURN {var}.name AS name, {var}.file AS file, {var}.line AS line, {var}.end_line AS end_line
        ORDER BY {var}.file, {var}.line
    """)


def _files_with(label: str) -> list[dict[str, str]]:
    """The files that hold a node with `label`."""
    return q(f"""
        MATCH (n:{label})
        RETURN DISTINCT n.file AS file
        ORDER BY file
    """)


@mcp.tool()
def list_test_functions() -> list[dict[str, Any]]:
    """
    List all test functions.

    Returns:
        List of test functions with their names, files, and line numbers
    """
    return _defined("f", "TestFunction")

@mcp.tool()
def list_example_functions() -> list[dict[str, Any]]:
    """
    List all example functions.

    Returns:
        List of example functions with their names, files, and line numbers
    """
    return _defined("f", "ExampleFunction")

@mcp.tool()
def list_test_classes() -> list[dict[str, Any]]:
    """
    List all test classes.

    Returns:
        List of test classes with their names, files, and line numbers
    """
    return _defined("c", "TestClass")

@mcp.tool()
def list_example_classes() -> list[dict[str, Any]]:
    """
    List all example classes.

    Returns:
        List of example classes with their names, files, and line numbers
    """
    return _defined("c", "ExampleClass")

@mcp.tool()
def get_test_files() -> list[dict[str, str]]:
    """
    List all files containing tests.

    Returns:
        List of file paths containing test components
    """
    return _files_with("Test")

@mcp.tool()
def get_example_files() -> list[dict[str, str]]:
    """
    List all files containing examples.

    Returns:
        List of file paths containing example components
    """
    return _files_with("Example")

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
