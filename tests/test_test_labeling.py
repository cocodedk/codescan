import os
import sys
import tempfile
import shutil
import unittest
import ast
from unittest.mock import MagicMock

# Add parent directory to path to import scanner module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import the module we'll be testing
from codescan_lib.analyzer import CodeAnalyzer

class TestTestLabeling(unittest.TestCase):
    """Test the test component labeling functionality."""

    def setUp(self):
        """Set up the test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.session_mock = MagicMock()

        # Create a sample test file
        self.test_file_path = os.path.join(self.temp_dir, "test_file.py")
        with open(self.test_file_path, "w") as f:
            f.write("""
class TestExample:
    def test_something(self):
        pass

def test_function():
    pass
""")

        # Create a regular file
        self.regular_file_path = os.path.join(self.temp_dir, "regular_file.py")
        with open(self.regular_file_path, "w") as f:
            f.write("""
class RegularClass:
    def regular_function(self):
        pass

def another_function():
    pass
""")

    def tearDown(self):
        """Clean up the temporary directory."""
        shutil.rmtree(self.temp_dir)

    def test_class_labeling_in_test_file(self):
        """Test that classes in test files get the Test and TestClass labels."""
        # Parse the test file
        with open(self.test_file_path, "r") as f:
            tree = ast.parse(f.read(), filename=self.test_file_path)

        # Create an analyzer with is_test_file=True
        analyzer = CodeAnalyzer(self.test_file_path, self.session_mock, is_test_file=True)

        # Reset the mock
        self.session_mock.reset_mock()

        # Visit the class node
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == "TestExample":
                analyzer.visit_ClassDef(node)
                break

        # Verify the correct Cypher query was called with Test and TestClass labels
        # We don't check the number of calls because visit_ClassDef calls generic_visit
        # which processes child nodes
        found_class_query = False
        for call in self.session_mock.run.call_args_list:
            query = call[0][0]
            if "MERGE (c:Class:Test:TestClass" in query:
                found_class_query = True
                break

        self.assertTrue(found_class_query, "Class query with Test and TestClass labels not found")

    def test_function_labeling_in_test_file(self):
        """Test that functions in test files get the Test and TestFunction labels."""
        # Parse the test file
        with open(self.test_file_path, "r") as f:
            tree = ast.parse(f.read(), filename=self.test_file_path)

        # Create an analyzer with is_test_file=True
        analyzer = CodeAnalyzer(self.test_file_path, self.session_mock, is_test_file=True)

        # Reset mock and visit the function node
        self.session_mock.reset_mock()
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "test_function":
                analyzer.visit_FunctionDef(node)
                break

        # Verify the call arguments to session.run
        self.assertIn("Function:Test:TestFunction", self.session_mock.run.call_args_list[0][0][0])

    def test_class_labeling_in_regular_file(self):
        """Test that classes in regular files don't get test labels."""
        # Parse the regular file
        with open(self.regular_file_path, "r") as f:
            tree = ast.parse(f.read(), filename=self.regular_file_path)

        # Create an analyzer with is_test_file=False
        analyzer = CodeAnalyzer(self.regular_file_path, self.session_mock, is_test_file=False)

        # Reset mock and visit the class node
        self.session_mock.reset_mock()
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == "RegularClass":
                analyzer.visit_ClassDef(node)
                break

        # Verify the call to session.run doesn't include test labels
        query = self.session_mock.run.call_args[0][0]
        self.assertNotIn("Test", query)
        self.assertNotIn("TestClass", query)

    def test_function_labeling_in_regular_file(self):
        """Test that functions in regular files don't get test labels."""
        # Parse the regular file
        with open(self.regular_file_path, "r") as f:
            tree = ast.parse(f.read(), filename=self.regular_file_path)

        # Create an analyzer with is_test_file=False
        analyzer = CodeAnalyzer(self.regular_file_path, self.session_mock, is_test_file=False)

        # Reset mock and visit the function node
        self.session_mock.reset_mock()
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "another_function":
                analyzer.visit_FunctionDef(node)
                break

        # Verify the call to session.run doesn't include test labels
        self.assertNotIn("Test", self.session_mock.run.call_args_list[0][0][0])
        self.assertNotIn("TestFunction", self.session_mock.run.call_args_list[0][0][0])


if __name__ == "__main__":
    unittest.main()
