import os
import sys
import unittest
from unittest.mock import patch

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import MCP tools to test
from codescan_lib.mcp_tools.test_tools import (
    list_test_functions, list_test_classes, get_test_files
)

class TestTestMCPTools(unittest.TestCase):
    """Test the MCP tools for test components."""

    @patch('codescan_lib.mcp_tools.test_tools.q')
    def test_list_test_functions(self, mock_q):
        """Test the list_test_functions tool."""
        # Set up mock return value
        mock_q.return_value = [
            {"name": "test_function1", "file": "tests/test_file1.py", "line": 10, "end_line": 15},
            {"name": "test_function2", "file": "tests/test_file2.py", "line": 20, "end_line": 25}
        ]

        # Call the function
        result = list_test_functions()

        # Assert the query was called with the correct Cypher query
        mock_q.assert_called_once()
        query = mock_q.call_args[0][0]
        self.assertIn("MATCH (f:TestFunction)", query)

        # Assert the result is what we expect
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["name"], "test_function1")
        self.assertEqual(result[1]["file"], "tests/test_file2.py")

    @patch('codescan_lib.mcp_tools.test_tools.q')
    def test_list_test_classes(self, mock_q):
        """Test the list_test_classes tool."""
        # Set up mock return value
        mock_q.return_value = [
            {"name": "TestClass1", "file": "tests/test_file1.py", "line": 5, "end_line": 30},
            {"name": "TestClass2", "file": "tests/test_file2.py", "line": 15, "end_line": 40}
        ]

        # Call the function
        result = list_test_classes()

        # Assert the query was called with the correct Cypher query
        mock_q.assert_called_once()
        query = mock_q.call_args[0][0]
        self.assertIn("MATCH (c:TestClass)", query)

        # Assert the result is what we expect
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["name"], "TestClass1")
        self.assertEqual(result[1]["file"], "tests/test_file2.py")

    @patch('codescan_lib.mcp_tools.test_tools.q')
    def test_get_test_files(self, mock_q):
        """Test the get_test_files tool."""
        # Set up mock return value
        mock_q.return_value = [
            {"file": "tests/test_file1.py"},
            {"file": "tests/test_file2.py"}
        ]

        # Call the function
        result = get_test_files()

        # Assert the query was called with the correct Cypher query
        mock_q.assert_called_once()
        query = mock_q.call_args[0][0]
        self.assertIn("MATCH (n:Test)", query)
        self.assertIn("RETURN DISTINCT n.file", query)

        # Assert the result is what we expect
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["file"], "tests/test_file1.py")
        self.assertEqual(result[1]["file"], "tests/test_file2.py")

    def test_test_detection_config(self):
        """Test the test_detection_config tool using a mock for the constants import."""
        # Mock the constants in codescan_lib
        with patch('codescan_lib.constants.TEST_DIR_PATTERNS', ["tests/", "test/"]), \
             patch('codescan_lib.constants.TEST_FILE_PATTERNS', ["test_*.py", "*_test.py"]), \
             patch('codescan_lib.constants.TEST_FUNCTION_PREFIXES', ["test_"]), \
             patch('codescan_lib.constants.TEST_CLASS_PATTERNS', ["Test*", "*Test"]):

            # Import the function to test
            from codescan_lib.mcp_tools.test_tools import get_test_detection_config

            # Call the function
            result = get_test_detection_config()

            # Assert the result is what we expect
            self.assertEqual(result["test_dir_patterns"], ["tests/", "test/"])
            self.assertEqual(result["test_file_patterns"], ["test_*.py", "*_test.py"])
            self.assertEqual(result["test_function_prefixes"], ["test_"])
            self.assertEqual(result["test_class_patterns"], ["Test*", "*Test"])


if __name__ == "__main__":
    unittest.main()
