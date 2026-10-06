"""
Statistics collector for code scanning.

This module provides a class to collect and display statistics about the code scanning process,
replacing the verbose print statements with a more organized approach.
"""

import time
from collections import Counter
from typing import Any

from .constants import (
    FILE_TYPE_EXAMPLE,
    FILE_TYPE_PRODUCTION,
    FILE_TYPE_TEST,
    STAT_CALLS,
    STAT_CLASSES,
    STAT_CONSTANTS,
    STAT_FUNCTIONS,
    STAT_IMPORTS,
    STAT_REFERENCE_FUNCTIONS,
    STAT_TEST_CLASSES,
    STAT_TEST_FUNCTIONS,
)
from .stats_report import print_summary


class StatsCollector:
    """Collects statistics during code scanning and provides methods to display them."""

    def __init__(self, verbose: bool = False) -> None:
        """Initialize the statistics collector."""
        self.verbose = verbose
        self.start_time = time.time()

        # Counters for different elements
        self.files_scanned = 0
        self.files_skipped = 0
        self.files_error = 0

        # Type counters
        self.elements = Counter({
            STAT_CLASSES: 0,
            STAT_FUNCTIONS: 0,
            STAT_CONSTANTS: 0,
            STAT_CALLS: 0,
            STAT_IMPORTS: 0,
            STAT_REFERENCE_FUNCTIONS: 0,
            STAT_TEST_FUNCTIONS: 0,
            STAT_TEST_CLASSES: 0
        })

        # File type counters
        self.file_types = Counter({
            FILE_TYPE_PRODUCTION: 0,
            FILE_TYPE_TEST: 0,
            FILE_TYPE_EXAMPLE: 0
        })

        # Sets to track unique elements
        self.unique_files: set[str] = set()
        self.unique_classes: set[str] = set()
        self.unique_functions: set[str] = set()

        # Error tracking
        self.errors: list[dict[str, Any]] = []

    def register_file(self, file_path: str, file_type: str) -> None:
        """Register a file that's being analyzed."""
        self.files_scanned += 1
        self.file_types[file_type] += 1
        self.unique_files.add(file_path)

        if self.verbose:
            print(f"Analyzing file: {file_path} - {file_type} file")

    def register_skipped_file(self, file_path: str, reason: str) -> None:
        """Register a file that's being skipped."""
        self.files_skipped += 1

        if self.verbose:
            print(f"Skipping file: {file_path} - {reason}")

    def register_file_error(self, file_path: str, error_type: str, error_msg: str) -> None:
        """Register an error that occurred during file analysis."""
        self.files_error += 1
        self.errors.append({
            'file': file_path,
            'type': error_type,
            'message': error_msg
        })

        if self.verbose:
            print(f"Error in file {file_path}: {error_type} - {error_msg}")

    def register_class(self, name: str, file_path: str, line: int, is_test: bool = False, is_example: bool = False) -> None:
        """Register a class that's found during analysis."""
        self.elements[STAT_CLASSES] += 1
        self.unique_classes.add(f"{file_path}:{name}")

        if is_test:
            self.elements[STAT_TEST_CLASSES] += 1

        if self.verbose:
            print(f"Found class: {name} in {file_path} at line {line}")

    def register_function(self, name: str, file_path: str, line: int, is_test: bool = False,
                         is_reference: bool = False, length: int = 0) -> None:
        """Register a function that's found during analysis."""
        self.elements[STAT_FUNCTIONS] += 1
        self.unique_functions.add(f"{file_path}:{name}")

        if is_test:
            self.elements[STAT_TEST_FUNCTIONS] += 1

        if is_reference:
            self.elements[STAT_REFERENCE_FUNCTIONS] += 1

        if self.verbose:
            print(f"Found function: {name} in {file_path} at line {line}{' (reference)' if is_reference else ''}")

    def register_constant(self, name: str, file_path: str, line: int, value: str, type_name: str) -> None:
        """Register a constant that's found during analysis."""
        self.elements[STAT_CONSTANTS] += 1

        if self.verbose:
            print(f"Found constant: {name} = {value} ({type_name}) in {file_path} at line {line}")

    def register_call(self, caller: str, callee: str, file_path: str, line: int, args: str = "") -> None:
        """Register a function call that's found during analysis."""
        self.elements[STAT_CALLS] += 1

        if self.verbose:
            print(f"Found call: {caller} -> {callee} in {file_path} at line {line}")

    def register_import(self, name: str, file_path: str, is_test: bool = False) -> None:
        """Register an import that's found during analysis."""
        self.elements[STAT_IMPORTS] += 1

        if self.verbose and is_test:
            print(f"Found import in test file: {name} in {file_path}")

    def set_reference_functions(self, count: int) -> None:
        """Set the number of callee names no definition was found for (known only after calls are resolved)."""
        self.elements[STAT_REFERENCE_FUNCTIONS] = count

    def get_summary(self) -> dict[str, Any]:
        """
        Get a summary of the collected statistics.

        Returns:
            Dictionary with summary statistics
        """
        elapsed_time = time.time() - self.start_time

        return {
            'time_elapsed': elapsed_time,
            'files': {
                'total': self.files_scanned,
                'skipped': self.files_skipped,
                'error': self.files_error,
                'by_type': dict(self.file_types)
            },
            'elements': dict(self.elements),
            'unique': {
                'files': len(self.unique_files),
                STAT_CLASSES: len(self.unique_classes),
                STAT_FUNCTIONS: len(self.unique_functions)
            },
            'errors': self.errors
        }

    def print_summary(self) -> None:
        """Print a summary of the collected statistics."""
        print_summary(self.get_summary())
