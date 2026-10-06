import ast
import fnmatch
import os
import sys
from pathlib import Path
from typing import Any

from .constants import TEST_DIR_PATTERNS, TEST_FILE_PATTERNS


def is_stdlib_module(module_name: str) -> bool:
    """Check if a module is part of the Python standard library."""
    return module_name.split(".")[0] in sys.stdlib_module_names

def project_roots(base_dir: str) -> set[str]:
    """Names a project import can start with: the scanned directory's top-level packages and modules."""
    return {
        entry.name[:-3] if entry.is_file() else entry.name
        for entry in os.scandir(base_dir)
        if entry.is_dir() or entry.name.endswith(".py")
    }


def node_span(node: ast.AST) -> tuple[int, int, int]:
    """Return (first line, last line, length in lines) of an AST node."""
    line = getattr(node, "lineno", -1)
    end_line = getattr(node, "end_lineno", -1)
    length = end_line - line + 1 if line >= 0 and end_line >= 0 else 0
    return line, end_line, length

def is_example_file(file_path: str) -> bool:
    """
    Determine if a file is in the examples directory.

    Args:
        file_path: Path to the file to check

    Returns:
        bool: True if the file is in examples directory, False otherwise
    """
    return 'examples' in os.path.normpath(file_path).replace('\\', '/').split('/')

def is_test_file(file_path: str, custom_patterns: dict[str, Any] | None = None) -> bool:
    """
    Determine if a file is a test file based on configured patterns.

    Args:
        file_path: Path to the file to check
        custom_patterns: Dictionary with custom patterns to use instead of defaults

    Returns:
        bool: True if the file is a test file, False otherwise
    """
    # Explicitly exclude examples directory files
    if is_example_file(file_path):
        return False

    # Use custom patterns if provided, otherwise use defaults
    dir_patterns = custom_patterns['test_dirs'] if custom_patterns and 'test_dirs' in custom_patterns else TEST_DIR_PATTERNS
    file_patterns = custom_patterns['test_files'] if custom_patterns and 'test_files' in custom_patterns else TEST_FILE_PATTERNS

    normalized_path = os.path.normpath(file_path).replace('\\', '/')
    path_parts = normalized_path.split('/')

    # Check if any directory in the path matches test directory patterns
    for part in path_parts:
        for pattern in dir_patterns:
            pattern_clean = pattern.rstrip('/')
            if part == pattern_clean:
                return True

    # Check if filename matches test file patterns
    filename = os.path.basename(file_path)
    for pattern in file_patterns:
        if fnmatch.fnmatch(filename, pattern):
            return True

    return False

def is_project_file(file_path: str, base_dir: str) -> bool:
    """Check if a file is part of the project (not in standard library)."""
    abs_path = os.path.abspath(file_path)
    return Path(abs_path).is_relative_to(os.path.abspath(base_dir))

def get_relative_path(file_path: str, base_dir: str) -> str:
    """Convert absolute file path to path relative to the project directory."""
    abs_file_path = os.path.abspath(file_path)
    abs_base_dir = os.path.abspath(base_dir)

    # Ensure the path is inside the base_dir
    if not is_project_file(abs_file_path, abs_base_dir):
        return file_path

    return os.path.relpath(abs_file_path, abs_base_dir)
