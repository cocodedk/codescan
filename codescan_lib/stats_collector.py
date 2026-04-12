"""
Statistics collector for code scanning.

This module provides a class to collect and display statistics about the code scanning process,
replacing the verbose print statements with a more organized approach.
"""

from collections import Counter
from typing import Dict, List, Any, Set
import time

class StatsCollector:
    """
    Collects statistics during code scanning and provides methods to display them.
    """

    def __init__(self, verbose: bool = False):
        """
        Initialize the statistics collector.

        Args:
            verbose: Whether to print verbose output during scanning
        """
        self.verbose = verbose
        self.start_time = time.time()

        # Counters for different elements
        self.files_scanned = 0
        self.files_skipped = 0
        self.files_error = 0

        # Type counters
        self.elements = Counter({
            'classes': 0,
            'functions': 0,
            'constants': 0,
            'calls': 0,
            'imports': 0,
            'reference_functions': 0,
            'test_functions': 0,
            'test_classes': 0
        })

        # File type counters
        self.file_types = Counter({
            'production': 0,
            'test': 0,
            'example': 0
        })

        # Sets to track unique elements
        self.unique_files: Set[str] = set()
        self.unique_classes: Set[str] = set()
        self.unique_functions: Set[str] = set()

        # Error tracking
        self.errors: List[Dict[str, Any]] = []

    def register_file(self, file_path: str, file_type: str) -> None:
        """
        Register a file that's being analyzed.

        Args:
            file_path: Path to the file
            file_type: Type of file (production, test, example)
        """
        self.files_scanned += 1
        self.file_types[file_type] += 1
        self.unique_files.add(file_path)

        if self.verbose:
            print(f"Analyzing file: {file_path} - {file_type} file")

    def register_skipped_file(self, file_path: str, reason: str) -> None:
        """
        Register a file that's being skipped.

        Args:
            file_path: Path to the file
            reason: Reason for skipping
        """
        self.files_skipped += 1

        if self.verbose:
            print(f"Skipping file: {file_path} - {reason}")

    def register_file_error(self, file_path: str, error_type: str, error_msg: str) -> None:
        """
        Register an error that occurred during file analysis.

        Args:
            file_path: Path to the file
            error_type: Type of error
            error_msg: Error message
        """
        self.files_error += 1
        self.errors.append({
            'file': file_path,
            'type': error_type,
            'message': error_msg
        })

        if self.verbose:
            print(f"Error in file {file_path}: {error_type} - {error_msg}")

    def register_class(self, name: str, file_path: str, line: int, is_test: bool = False, is_example: bool = False) -> None:
        """
        Register a class that's found during analysis.

        Args:
            name: Name of the class
            file_path: Path to the file
            line: Line number
            is_test: Whether it's a test class
            is_example: Whether it's an example class
        """
        self.elements['classes'] += 1
        self.unique_classes.add(f"{file_path}:{name}")

        if is_test:
            self.elements['test_classes'] += 1

        if self.verbose:
            print(f"Found class: {name} in {file_path} at line {line}")

    def register_function(self, name: str, file_path: str, line: int, is_test: bool = False,
                         is_reference: bool = False, length: int = 0) -> None:
        """
        Register a function that's found during analysis.

        Args:
            name: Name of the function
            file_path: Path to the file
            line: Line number
            is_test: Whether it's a test function
            is_reference: Whether it's a reference function
            length: Length of the function in lines
        """
        self.elements['functions'] += 1
        self.unique_functions.add(f"{file_path}:{name}")

        if is_test:
            self.elements['test_functions'] += 1

        if is_reference:
            self.elements['reference_functions'] += 1

        if self.verbose:
            print(f"Found function: {name} in {file_path} at line {line}{' (reference)' if is_reference else ''}")

    def register_constant(self, name: str, file_path: str, line: int, value: str, type_name: str) -> None:
        """
        Register a constant that's found during analysis.

        Args:
            name: Name of the constant
            file_path: Path to the file
            line: Line number
            value: Value of the constant
            type_name: Type of the constant
        """
        self.elements['constants'] += 1

        if self.verbose:
            print(f"Found constant: {name} = {value} ({type_name}) in {file_path} at line {line}")

    def register_call(self, caller: str, callee: str, file_path: str, line: int, args: str = "") -> None:
        """
        Register a function call that's found during analysis.

        Args:
            caller: Name of the calling function
            callee: Name of the called function
            file_path: Path to the file
            line: Line number
            args: Arguments of the call
        """
        self.elements['calls'] += 1

        if self.verbose:
            print(f"Found call: {caller} -> {callee} in {file_path} at line {line}")

    def register_import(self, name: str, file_path: str, is_test: bool = False) -> None:
        """
        Register an import that's found during analysis.

        Args:
            name: Name of the imported module/object
            file_path: Path to the file
            is_test: Whether it's in a test file
        """
        self.elements['imports'] += 1

        if self.verbose and is_test:
            print(f"Found import in test file: {name} in {file_path}")

    def get_summary(self) -> Dict[str, Any]:
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
                'classes': len(self.unique_classes),
                'functions': len(self.unique_functions)
            },
            'errors': self.errors
        }

    def print_summary(self) -> None:
        """
        Print a summary of the collected statistics.
        """
        summary = self.get_summary()
        elapsed = summary['time_elapsed']

        print("\n=== Code Scanning Summary ===")
        print(f"Time elapsed: {elapsed:.2f} seconds")
        print(f"Files scanned: {summary['files']['total']} ({summary['files']['skipped']} skipped, {summary['files']['error']} errors)")
        print(f"File types: {summary['files']['by_type']}")
        print("Elements found:")
        for name, count in summary['elements'].items():
            print(f"  - {name}: {count}")

        print("Unique elements:")
        for name, count in summary['unique'].items():
            print(f"  - {name}: {count}")

        if summary['errors']:
            print(f"\nErrors encountered: {len(summary['errors'])}")
            for error in summary['errors'][:5]:  # Show first 5 errors
                print(f"  - {error['file']}: {error['type']} - {error['message']}")

            if len(summary['errors']) > 5:
                print(f"  ... and {len(summary['errors']) - 5} more errors")

        print("=== End of Summary ===")
