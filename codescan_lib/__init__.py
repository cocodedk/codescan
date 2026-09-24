"""
CodeScan Library - A library for code analysis and graph database construction.

This package contains modules for analyzing Python code and constructing a graph
database representation of the code structure using Neo4j.
"""

from .analysis import analyze_directory, analyze_file
from .analyzer import CodeAnalyzer
from .constants import (
    BUILTIN_FUNCTIONS,
    IGNORE_DIRS,
    NEO4J_HOST,
    NEO4J_PASSWORD,
    NEO4J_PORT_BOLT,
    NEO4J_URI,
    NEO4J_USER,
    TEST_CLASS_PATTERNS,
    TEST_DIR_PATTERNS,
    TEST_FILE_PATTERNS,
    TEST_FUNCTION_PREFIXES,
)
from .db_operations import (
    clear_database,
    close_db_connection,
    get_db_session,
    print_db_info,
)
from .utils import (
    get_relative_path,
    is_example_file,
    is_project_file,
    is_stdlib_module,
    is_test_file,
)

# Grouped by category rather than isort's global casing sort -- a blind
# alphabetical sort would interleave constants, functions and classes and
# make the grouping comments below misleading, so this is sorted within
# each category instead.
__all__ = [  # noqa: RUF022
    # Constants
    'BUILTIN_FUNCTIONS', 'IGNORE_DIRS', 'NEO4J_HOST', 'NEO4J_PASSWORD', 'NEO4J_PORT_BOLT',
    'NEO4J_URI', 'NEO4J_USER', 'TEST_CLASS_PATTERNS', 'TEST_DIR_PATTERNS', 'TEST_FILE_PATTERNS',
    'TEST_FUNCTION_PREFIXES',

    # Utility functions
    'get_relative_path', 'is_example_file', 'is_project_file', 'is_stdlib_module', 'is_test_file',

    # Classes
    'CodeAnalyzer',

    # Database operations
    'clear_database', 'close_db_connection', 'get_db_session', 'print_db_info',

    # Analysis functions
    'analyze_directory', 'analyze_file',
]
