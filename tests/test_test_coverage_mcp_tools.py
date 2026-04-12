import os
import sys
import unittest
from unittest.mock import patch

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

class TestCoverageMCPTools(unittest.TestCase):
    """Test the MCP tools for test coverage."""

    @patch('codescan_lib.mcp_tools.test_tools.q')
    def test_untested_functions(self, mock_q):
        """Test the untested_functions tool."""
        # Import the function to test
        from codescan_lib.mcp_tools.test_tools import untested_functions

        # Set up mock return value
        mock_q.return_value = [
            {"name": "untested_func1", "file": "scanner.py", "line": 10},
            {"name": "untested_func2", "file": "scanner.py", "line": 20}
        ]

        # Call the function
        result = untested_functions()

        # Assert the query was called with the correct Cypher query
        mock_q.assert_called_once()
        query = mock_q.call_args[0][0]

        # The query should be looking for functions that are not test functions and don't have a TESTS relationship
        self.assertIn("MATCH (f:Function)", query)
        self.assertIn("NOT f:TestFunction", query)
        self.assertIn("NOT (:TestFunction)-[:TESTS]->(f)", query)

        # Assert the result is what we expect
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["name"], "untested_func1")
        self.assertEqual(result[1]["file"], "scanner.py")

    @patch('codescan_lib.mcp_tools.test_tools.q')
    def test_test_coverage_ratio(self, mock_q):
        """Test the test_coverage_ratio tool."""
        # Import the function to test
        from codescan_lib.mcp_tools.test_tools import get_test_coverage_ratio

        # Set up mock return value
        mock_q.return_value = [
            {"total_functions": 10, "tested_functions": 7, "coverage_ratio": 0.7}
        ]

        # Call the function
        result = get_test_coverage_ratio()

        # Assert the query was called with the correct Cypher query
        mock_q.assert_called_once()
        query = mock_q.call_args[0][0]

        # The query should calculate total functions, tested functions, and the ratio
        self.assertIn("MATCH (f:Function) WHERE NOT f:TestFunction", query)
        self.assertIn("count(f) AS total_functions", query)
        self.assertIn("(:TestFunction)-[:TESTS]->(f)", query)
        self.assertIn("count(f) AS tested_functions", query)
        self.assertIn("toFloat(tested_functions) / total_functions", query)

        # Assert the result is what we expect
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["total_functions"], 10)
        self.assertEqual(result[0]["tested_functions"], 7)
        self.assertEqual(result[0]["coverage_ratio"], 0.7)

    @patch('codescan_lib.mcp_tools.test_tools.q')
    def test_functions_tested_by(self, mock_q):
        """Test the functions_tested_by tool."""
        # Import the function to test
        from codescan_lib.mcp_tools.test_tools import functions_tested_by

        # Set up mock return value
        mock_q.return_value = [
            {"tested_name": "analyze_file", "tested_file": "scanner.py", "method": "naming_pattern"},
            {"tested_name": "CodeAnalyzer.visit_Call", "tested_file": "scanner.py", "method": "import"}
        ]

        # Call the function
        result = functions_tested_by("test_scanner.py")

        # Assert the query was called with the correct Cypher query
        mock_q.assert_called_once()
        query = mock_q.call_args[0][0]
        params = mock_q.call_args[1]

        # The query should find functions tested by the specified test file
        self.assertIn("MATCH (test:TestFunction {file: $file})-[r:TESTS]->(f:Function)", query)
        self.assertEqual(params.get("file"), "test_scanner.py")
        self.assertIn("f.name AS tested_name", query)
        self.assertIn("f.file AS tested_file", query)
        self.assertIn("r.method AS method", query)

        # Assert the result is what we expect
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["tested_name"], "analyze_file")
        self.assertEqual(result[1]["tested_file"], "scanner.py")
        self.assertEqual(result[0]["method"], "naming_pattern")

    @patch('codescan_lib.mcp_tools.test_tools.q')
    def test_tests_for_function(self, mock_q):
        """Test the tests_for_function tool."""
        # Import the function to test
        from codescan_lib.mcp_tools.test_tools import get_tests_for_function

        # Set up mock return value
        mock_q.return_value = [
            {"test_name": "test_analyze_file", "test_file": "tests/test_scanner.py", "method": "naming_pattern"},
            {"test_name": "TestScanner.test_complex_case", "test_file": "tests/test_scanner.py", "method": "call"}
        ]

        # Call the function
        result = get_tests_for_function("analyze_file", "scanner.py")

        # Assert the query was called with the correct Cypher query
        mock_q.assert_called_once()
        query = mock_q.call_args[0][0]
        params = mock_q.call_args[1]

        # The query should find test functions that test the specified function
        self.assertIn("MATCH (test:TestFunction)-[r:TESTS]->(f:Function {name: $name", query)
        self.assertEqual(params.get("name"), "analyze_file")
        self.assertEqual(params.get("file"), "scanner.py")
        self.assertIn("test.name AS test_name", query)
        self.assertIn("test.file AS test_file", query)
        self.assertIn("r.method AS method", query)

        # Assert the result is what we expect
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["test_name"], "test_analyze_file")
        self.assertEqual(result[1]["test_file"], "tests/test_scanner.py")
        self.assertEqual(result[0]["method"], "naming_pattern")

if __name__ == "__main__":
    unittest.main()
