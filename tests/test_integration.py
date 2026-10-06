import os
import shutil
import tempfile

import pytest
from neo4j import GraphDatabase
from project_builders import ProjectBuilders

from codescan_lib import (
    analyze_directory,
    clear_database,
)


@pytest.fixture(scope="module")
def neo4j_test_session():
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7600")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "demodemo")
    driver = GraphDatabase.driver(uri, auth=(user, password))
    with driver.session() as session:
        yield session
    driver.close()

class TestIntegration(ProjectBuilders):
    """Integration tests for test labeling and test coverage detection."""

    def test_standard_project_structure(self, neo4j_test_session):
        """Test detection of test components in a standard project structure."""
        # Create a temporary project directory
        temp_dir = tempfile.mkdtemp()
        try:
            # Set up the project
            self.setup_standard_project(temp_dir)

            # Clear database and analyze the project
            clear_database(neo4j_test_session)
            analyze_directory(temp_dir, neo4j_test_session)

            # Verify test functions were detected
            result = neo4j_test_session.run(
                "MATCH (f:TestFunction) RETURN count(f) AS count"
            ).single()
            assert result["count"] == 2, "Should detect 2 test functions"

            # Verify TESTS relationships were created
            result = neo4j_test_session.run(
                "MATCH ()-[r:TESTS]->() RETURN count(r) AS count"
            ).single()
            assert result["count"] > 0, "Should create TESTS relationships"

            # Verify test coverage for specific functions
            result = neo4j_test_session.run(
                "MATCH (:TestFunction)-[:TESTS]->(f:Function {name: 'add'}) RETURN count(f) AS count"
            ).single()
            assert result["count"] > 0, "Should detect test coverage for add function"

            result = neo4j_test_session.run(
                "MATCH (:TestFunction)-[:TESTS]->(f:Function {name: 'multiply'}) RETURN count(f) AS count"
            ).single()
            assert result["count"] == 0, "Should not have test coverage for multiply function"

        finally:
            # Clean up
            shutil.rmtree(temp_dir)

    def test_module_tests_structure(self, neo4j_test_session):
        """Test detection of test components in a module tests structure."""
        # Create a temporary project directory
        temp_dir = tempfile.mkdtemp()
        try:
            # Set up the project
            self.setup_module_tests_project(temp_dir)

            # Clear database and analyze the project
            clear_database(neo4j_test_session)
            analyze_directory(temp_dir, neo4j_test_session)

            # Verify test functions were detected
            result = neo4j_test_session.run(
                "MATCH (f:TestFunction) RETURN count(f) AS count"
            ).single()
            assert result["count"] >= 2, "Should detect at least 2 test functions"

            # Verify TESTS relationships were created
            result = neo4j_test_session.run(
                "MATCH ()-[r:TESTS]->() RETURN count(r) AS count"
            ).single()
            assert result["count"] > 0, "Should create TESTS relationships"

        finally:
            # Clean up
            shutil.rmtree(temp_dir)

    def test_spec_naming_convention(self, neo4j_test_session):
        """Test detection of test components with spec-style naming."""
        # Create a temporary project directory
        temp_dir = tempfile.mkdtemp()
        try:
            # Set up the project with spec naming
            self.setup_spec_naming_project(temp_dir)

            # Clear database and analyze the project
            clear_database(neo4j_test_session)
            analyze_directory(temp_dir, neo4j_test_session)

            # Verify test functions and classes were detected
            result = neo4j_test_session.run(
                "MATCH (f:TestFunction) RETURN count(f) AS count"
            ).single()
            assert result["count"] >= 4, "Should detect at least 4 test functions"

            result = neo4j_test_session.run(
                "MATCH (c:TestClass) RETURN count(c) AS count"
            ).single()
            assert result["count"] >= 1, "Should detect at least 1 test class"

            # Verify TESTS relationships were created
            result = neo4j_test_session.run(
                "MATCH ()-[r:TESTS]->() RETURN count(r) AS count"
            ).single()
            assert result["count"] > 0, "Should create TESTS relationships"

        finally:
            # Clean up
            shutil.rmtree(temp_dir)
            self.restore_config()
