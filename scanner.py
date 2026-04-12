#!/usr/bin/env python3
"""
Code Scanner - A tool for analyzing Python code and building a Neo4j graph database.

This script scans Python files in a specified directory, analyzes the code structure,
and creates a graph database representation in Neo4j.
"""

import os
import argparse
from neo4j import GraphDatabase

from codescan_lib import (
    # Constants
    NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, TEST_DIR_PATTERNS, TEST_FILE_PATTERNS, TEST_FUNCTION_PREFIXES, TEST_CLASS_PATTERNS,
    IGNORE_DIRS,

    # Database operations
    clear_database, print_db_info,

    # Analysis functions
    analyze_directory
)

def main():
    """Main function to parse arguments and run the scanner."""
    # Initialize pattern variables with defaults from the module
    test_dir_patterns = list(TEST_DIR_PATTERNS)
    test_file_patterns = list(TEST_FILE_PATTERNS)
    test_function_prefixes = list(TEST_FUNCTION_PREFIXES)
    test_class_patterns = list(TEST_CLASS_PATTERNS)

    parser = argparse.ArgumentParser(description='Scan Python code and build a Neo4j graph database')
    parser.add_argument('--project-dir', dest='project_dir',
                        default=os.getenv("PROJECT_DIR", "."),
                        help='Directory to scan (default: current directory or PROJECT_DIR env var)')

    # Configuration options
    parser.add_argument('--test-dirs', dest='test_dirs',
                        default=','.join(test_dir_patterns),
                        help='Comma-separated list of test directory patterns')
    parser.add_argument('--test-files', dest='test_files',
                        default=','.join(test_file_patterns),
                        help='Comma-separated list of test file patterns')
    parser.add_argument('--test-funcs', dest='test_funcs',
                        default=','.join(test_function_prefixes),
                        help='Comma-separated list of test function prefixes')
    parser.add_argument('--test-classes', dest='test_classes',
                        default=','.join(test_class_patterns),
                        help='Comma-separated list of test class patterns')

    # Output options
    parser.add_argument('--quiet', dest='quiet', action='store_true',
                        help='Reduce output verbosity')
    parser.add_argument('--verbose', dest='verbose', action='store_true',
                        help='Increase output verbosity')

    args = parser.parse_args()

    # Determine verbosity level
    verbose = args.verbose and not args.quiet
    quiet = args.quiet

    # Update configuration from command line arguments
    test_dir_patterns = args.test_dirs.split(',')
    test_file_patterns = args.test_files.split(',')
    test_function_prefixes = args.test_funcs.split(',')
    test_class_patterns = args.test_classes.split(',')

    # Create a dictionary with the custom patterns
    custom_patterns = {
        'test_dirs': test_dir_patterns,
        'test_files': test_file_patterns,
        'test_funcs': test_function_prefixes,
        'test_classes': test_class_patterns
    }

    project_dir = args.project_dir

    # Print basic info unless quiet mode is enabled
    if not quiet:
        print(f"Ignoring directories: {', '.join(IGNORE_DIRS)}")
        print(f"Connected to Neo4j at {NEO4J_URI}")
        print(f"Analyzing project at {project_dir}")

        # Print test detection configuration if verbose
        if verbose:
            print(f"Test directory patterns: {', '.join(test_dir_patterns)}")
            print(f"Test file patterns: {', '.join(test_file_patterns)}")
            print(f"Test function prefixes: {', '.join(test_function_prefixes)}")
            print(f"Test class patterns: {', '.join(test_class_patterns)}")

    # Get a database session
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    with driver.session() as session:
        # Clear the database to start fresh
        clear_database(session, quiet=quiet)

        # Analyze the directory with custom patterns and collect stats
        stats = analyze_directory(
            project_dir,
            session,
            custom_patterns=custom_patterns,
            verbose=verbose
        )

        # Print statistics summary
        if not quiet:
            stats.print_summary()

        # Print database information if not quiet
        print_db_info(quiet=quiet)

    # Close the connection
    driver.close()

if __name__ == "__main__":
    main()
