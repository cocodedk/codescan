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
from codescan_lib.utils import is_example_file

class TestExampleLabeling(unittest.TestCase):
    """Test the example component labeling functionality."""

    def setUp(self):
        """Set up the test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.session_mock = MagicMock()

        # Create examples directory
        self.examples_dir = os.path.join(self.temp_dir, "examples")
        os.makedirs(self.examples_dir)

        # Create a sample example file
        self.example_file_path = os.path.join(self.examples_dir, "example_class.py")
        with open(self.example_file_path, "w") as f:
            f.write("""
class ExampleClass:
    def example_method(self):
        pass

def example_function():
    pass
""")

        # Create a regular file (non-example)
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

    def test_is_example_file_detection(self):
        """Test the is_example_file function."""
        # Files in examples directory should be detected as examples
        self.assertTrue(is_example_file(self.example_file_path))

        # Regular files should not be detected as examples
        self.assertFalse(is_example_file(self.regular_file_path))

    def test_class_labeling_in_example_file(self):
        """Test that classes in example files get the Example and ExampleClass labels."""
        # Parse the example file
        with open(self.example_file_path, "r") as f:
            tree = ast.parse(f.read(), filename=self.example_file_path)

        # Create an analyzer with the example file
        analyzer = CodeAnalyzer(self.example_file_path, self.session_mock)

        # Reset the mock
        self.session_mock.reset_mock()

        # Visit the class node
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == "ExampleClass":
                analyzer.visit_ClassDef(node)
                break

        # Verify the correct Cypher query was called with Example and ExampleClass labels
        # We don't check the number of calls because visit_ClassDef calls generic_visit
        # which processes child nodes
        found_class_query = False
        for call in self.session_mock.run.call_args_list:
            query = call[0][0]
            if "MERGE (c:Class:Example:ExampleClass" in query:
                found_class_query = True
                break

        self.assertTrue(found_class_query, "Class query with Example and ExampleClass labels not found")

    def test_function_labeling_in_example_file(self):
        """Test that functions in example files get the Example and ExampleFunction labels."""
        # Parse the example file
        with open(self.example_file_path, "r") as f:
            tree = ast.parse(f.read(), filename=self.example_file_path)

        # Create an analyzer with the example file
        analyzer = CodeAnalyzer(self.example_file_path, self.session_mock)

        # Reset mock and visit the function node
        self.session_mock.reset_mock()
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "example_function":
                analyzer.visit_FunctionDef(node)
                break

        # Verify the call arguments to session.run
        self.assertIn("Function:Example:ExampleFunction", self.session_mock.run.call_args_list[0][0][0])

    def test_class_labeling_in_regular_file(self):
        """Test that classes in regular files don't get example labels."""
        # Parse the regular file
        with open(self.regular_file_path, "r") as f:
            tree = ast.parse(f.read(), filename=self.regular_file_path)

        # Create an analyzer with a regular file
        analyzer = CodeAnalyzer(self.regular_file_path, self.session_mock)

        # Reset mock and visit the class node
        self.session_mock.reset_mock()
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == "RegularClass":
                analyzer.visit_ClassDef(node)
                break

        # Verify the call to session.run doesn't include example labels
        query = self.session_mock.run.call_args[0][0]
        self.assertNotIn("Example", query)
        self.assertNotIn("ExampleClass", query)

    def test_function_labeling_in_regular_file(self):
        """Test that functions in regular files don't get example labels."""
        # Parse the regular file
        with open(self.regular_file_path, "r") as f:
            tree = ast.parse(f.read(), filename=self.regular_file_path)

        # Create an analyzer with a regular file
        analyzer = CodeAnalyzer(self.regular_file_path, self.session_mock)

        # Reset mock and visit the function node
        self.session_mock.reset_mock()
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef) and node.name == "another_function":
                analyzer.visit_FunctionDef(node)
                break

        # Verify the call to session.run doesn't include example labels
        self.assertNotIn("Example", self.session_mock.run.call_args_list[0][0][0])
        self.assertNotIn("ExampleFunction", self.session_mock.run.call_args_list[0][0][0])


if __name__ == "__main__":
    unittest.main()
