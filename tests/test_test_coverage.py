import ast
import os
import shutil
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

# Add parent directory to path to import scanner module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import the module we'll be testing
from codescan_lib.analysis import analyze_file
from codescan_lib.analyzer import CodeAnalyzer


class TestCoverageDetection(unittest.TestCase):
    """Test the test coverage detection functionality."""

    def setUp(self):
        """Set up the test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.session_mock = MagicMock()

        # Create a sample test file with imports and calls
        self.test_file_path = os.path.join(self.temp_dir, "test_file.py")
        with open(self.test_file_path, "w") as f:
            f.write("""
import codescan_lib  # Direct import
from codescan_lib.analyzer import CodeAnalyzer  # Import from

class TestCodeAnalyzer:
    def test_visit_call(self):
        analyzer = CodeAnalyzer("test.py", None)
        analyzer.visit_call(None)

def test_analyze_file():
    codescan_lib.analyze_file("test.py", None, ".")
""")

        # Create a production file that will be "tested"
        self.prod_file_path = os.path.join(self.temp_dir, "codescan_lib/analyzer.py")
        os.makedirs(os.path.dirname(self.prod_file_path), exist_ok=True)
        with open(self.prod_file_path, "w") as f:
            f.write("""
class CodeAnalyzer:
    def visit_call(self, node):
        pass
""")

        # Create a production file for analyze_file
        self.analysis_file_path = os.path.join(self.temp_dir, "codescan_lib/analysis.py")
        with open(self.analysis_file_path, "w") as f:
            f.write("""
def analyze_file(file_path, session, base_dir):
    pass
""")

    def tearDown(self):
        """Clean up the temporary directory."""
        shutil.rmtree(self.temp_dir)

    def test_visit_import_tracking(self):
        """Test that imports in test files are tracked correctly."""
        # Parse the test file
        with open(self.test_file_path, "r") as f:
            tree = ast.parse(f.read(), filename=self.test_file_path)

        # Create an analyzer with is_test_file=True
        analyzer = CodeAnalyzer(self.test_file_path, self.session_mock, is_test_file=True)

        # Find the Import node
        import_node = None
        for node in ast.walk(tree):
            if isinstance(node, ast.Import) and any(alias.name == "codescan_lib" for alias in node.names):
                import_node = node
                break

        # Call visit_Import with the node
        analyzer.visit_Import(import_node)

        # Verify the correct Cypher query was called to track the import
        found_import_tracking = False
        for call in self.session_mock.run.call_args_list:
            if "MERGE (i:Import" in call[0][0] and "codescan_lib" in str(call):
                found_import_tracking = True
                break

        self.assertTrue(found_import_tracking, "Import tracking not found in session calls")

    def test_visit_importfrom_tracking(self):
        """Test that import from statements in test files are tracked correctly."""
        # Parse the test file
        with open(self.test_file_path, "r") as f:
            tree = ast.parse(f.read(), filename=self.test_file_path)

        # Create an analyzer with is_test_file=True
        analyzer = CodeAnalyzer(self.test_file_path, self.session_mock, is_test_file=True)

        # Find the ImportFrom node
        importfrom_node = None
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module == "codescan_lib":
                importfrom_node = node
                break

        # Make sure we found an ImportFrom node
        if importfrom_node is None:
            # Create a custom ImportFrom node if none was found in the file
            print("Creating a custom ImportFrom node for testing")
            importfrom_node = ast.ImportFrom(
                module='codescan_lib',
                names=[ast.alias(name='CodeAnalyzer', asname=None)],
                level=0
            )
            # Add required line number attributes
            importfrom_node.lineno = 1
            if hasattr(ast, 'end_lineno'):  # Python 3.8+
                importfrom_node.end_lineno = 1

        # Call visit_ImportFrom with the node
        analyzer.visit_ImportFrom(importfrom_node)

        # Verify the correct Cypher query was called to track the import
        found_import_tracking = False
        for call in self.session_mock.run.call_args_list:
            if "MERGE (i:Import" in call[0][0] and "CodeAnalyzer" in str(call):
                found_import_tracking = True
                break

        self.assertTrue(found_import_tracking, "ImportFrom tracking not found in session calls")

    def test_process_test_relationships_naming(self):
        """Test that test relationships are created based on naming patterns."""
        # Create an analyzer with is_test_file=True
        analyzer = CodeAnalyzer(self.test_file_path, self.session_mock, is_test_file=True)

        # Call the method to create test relationships
        analyzer.process_test_relationships()

        # Verify the correct Cypher query was called to create naming-based relationships
        found_naming_relationship = False
        for call in self.session_mock.run.call_args_list:
            if "MATCH (test:TestFunction)" in call[0][0] and "STARTS WITH" in call[0][0] and "MERGE (test)-[:TESTS" in call[0][0]:
                found_naming_relationship = True
                break

        self.assertTrue(found_naming_relationship, "Naming-based test relationship creation not found")

    def test_process_test_relationships_imports(self):
        """Test that test relationships are created based on imports."""
        # Create an analyzer with is_test_file=True
        analyzer = CodeAnalyzer(self.test_file_path, self.session_mock, is_test_file=True)

        # Call the method to create test relationships
        analyzer.process_test_relationships()

        # Verify the correct Cypher query was called to create import-based relationships
        found_import_relationship = False
        for call in self.session_mock.run.call_args_list:
            if "MATCH (test:TestFunction)-[:IMPORTS]->(i:Import)" in call[0][0] and "MERGE (test)-[:TESTS" in call[0][0]:
                found_import_relationship = True
                break

        self.assertTrue(found_import_relationship, "Import-based test relationship creation not found")

    def test_process_test_relationships_calls(self):
        """Test that test relationships are created based on calls."""
        # Create an analyzer with is_test_file=True
        analyzer = CodeAnalyzer(self.test_file_path, self.session_mock, is_test_file=True)

        # Call the method to create test relationships
        analyzer.process_test_relationships()

        # Verify the correct Cypher query was called to create call-based relationships
        found_call_relationship = False
        for call in self.session_mock.run.call_args_list:
            if "MATCH (test:TestFunction)-[:CALLS]->(prod:Function)" in call[0][0] and "MERGE (test)-[:TESTS" in call[0][0]:
                found_call_relationship = True
                break

        self.assertTrue(found_call_relationship, "Call-based test relationship creation not found")

    def test_analyze_file_calls_process_test_relationships(self):
        """Test that analyze_file calls process_test_relationships for test files."""
        # Create a test file with a name that will definitely be detected as a test file
        test_file_path = os.path.join(self.temp_dir, "tests/test_example.py")
        os.makedirs(os.path.dirname(test_file_path), exist_ok=True)
        with open(test_file_path, "w") as f:
            f.write("""
import codescan_lib
from codescan_lib.analyzer import CodeAnalyzer

def test_something():
    pass
""")

        # Create a direct spy on the process_test_relationships method
        with patch.object(CodeAnalyzer, 'process_test_relationships') as mock_process:
            # Create a session mock
            session_mock = MagicMock()

            # Call analyze_file with the test file
            analyze_file(test_file_path, session_mock, self.temp_dir)

            # Verify process_test_relationships was called
            mock_process.assert_called_once()

if __name__ == "__main__":
    unittest.main()
