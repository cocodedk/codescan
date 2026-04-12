import os
import tempfile
import shutil
import pytest
from neo4j import GraphDatabase
from codescan_lib import (
    clear_database, analyze_directory,
    TEST_DIR_PATTERNS, TEST_FILE_PATTERNS, TEST_FUNCTION_PREFIXES, TEST_CLASS_PATTERNS
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

class TestIntegration:
    """Integration tests for test labeling and test coverage detection."""

    def setup_standard_project(self, base_dir):
        """Set up a standard project structure with tests in a tests directory."""
        # Create the project structure
        tests_dir = os.path.join(base_dir, "tests")
        os.makedirs(tests_dir)

        # Create production code file
        with open(os.path.join(base_dir, "calculator.py"), "w") as f:
            f.write("""
def add(a, b):
    return a + b

def subtract(a, b):
    return a - b

def multiply(a, b):
    return a * b
""")

        # Create test file
        with open(os.path.join(tests_dir, "test_calculator.py"), "w") as f:
            f.write("""
import calculator

def test_add():
    assert calculator.add(2, 3) == 5

def test_subtract():
    assert calculator.subtract(5, 3) == 2
""")

    def setup_module_tests_project(self, base_dir):
        """Set up a project structure with tests within module directories."""
        # Create the project structure
        calc_dir = os.path.join(base_dir, "calculator")
        os.makedirs(calc_dir)
        calc_tests_dir = os.path.join(calc_dir, "tests")
        os.makedirs(calc_tests_dir)

        # Create production code file
        with open(os.path.join(calc_dir, "operations.py"), "w") as f:
            f.write("""
def add(a, b):
    return a + b

def subtract(a, b):
    return a - b

def multiply(a, b):
    return a * b
""")

        # Create test file
        with open(os.path.join(calc_tests_dir, "test_operations.py"), "w") as f:
            f.write("""
from calculator.operations import add, subtract

def test_add():
    assert add(2, 3) == 5

def test_subtract():
    assert subtract(5, 3) == 2
""")

    def setup_spec_naming_project(self, base_dir):
        """Set up a project with spec-style test naming (BDD style)."""
        # Create the project structure
        spec_dir = os.path.join(base_dir, "spec")
        os.makedirs(spec_dir)

        # Create production code file
        with open(os.path.join(base_dir, "validator.py"), "w") as f:
            f.write("""
def is_email_valid(email):
    return "@" in email and "." in email

def is_password_strong(password):
    return len(password) >= 8 and any(c.isdigit() for c in password)
""")

        # Create spec file
        with open(os.path.join(spec_dir, "validator_spec.py"), "w") as f:
            f.write("""
import validator

class DescribeEmailValidator:
    def it_validates_valid_emails(self):
        assert validator.is_email_valid("test@example.com")

    def it_rejects_invalid_emails(self):
        assert not validator.is_email_valid("invalid")

def describe_password_validator():
    def it_accepts_strong_passwords():
        assert validator.is_password_strong("secureP4ss")

    def it_rejects_weak_passwords():
        assert not validator.is_password_strong("weak")
""")

        # Save the original configuration
        self.orig_dir_patterns = TEST_DIR_PATTERNS.copy()
        self.orig_file_patterns = TEST_FILE_PATTERNS.copy()
        self.orig_function_prefixes = TEST_FUNCTION_PREFIXES.copy()
        self.orig_class_patterns = TEST_CLASS_PATTERNS.copy()

        # Update configuration for spec-style testing
        TEST_DIR_PATTERNS.append("spec/")
        TEST_FILE_PATTERNS.append("*_spec.py")
        TEST_FUNCTION_PREFIXES.extend(["it_", "describe_"])
        TEST_CLASS_PATTERNS.append("Describe*")

    def restore_config(self):
        """Restore the original scanner configuration."""
        # Only restore if we've saved the original configuration
        if hasattr(self, 'orig_dir_patterns'):
            TEST_DIR_PATTERNS.clear()
            TEST_DIR_PATTERNS.extend(self.orig_dir_patterns)
            TEST_FILE_PATTERNS.clear()
            TEST_FILE_PATTERNS.extend(self.orig_file_patterns)
            TEST_FUNCTION_PREFIXES.clear()
            TEST_FUNCTION_PREFIXES.extend(self.orig_function_prefixes)
            TEST_CLASS_PATTERNS.clear()
            TEST_CLASS_PATTERNS.extend(self.orig_class_patterns)

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
