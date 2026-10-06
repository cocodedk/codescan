"""
Tests for the new CodeScan MCP tools:
- untested_classes
- transitive_calls
"""
import os
import sys
import unittest

# Add parent directory to path to import modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from mocked_queries import MockedQueries

# Import the tools we're testing
from codescan_lib.mcp_tools.call_graph import transitive_calls
from codescan_lib.mcp_tools.test_coverage_tools import untested_classes


class TestNewTools(MockedQueries):
    """Test the new tools added to the MCP server."""

    def test_untested_classes(self):
        """Test the untested_classes tool."""
        # Set up mock return value
        mock_results = [
            {"name": "UntestClass", "file": "example.py", "line": 10},
            {"name": "AnotherUntestClass", "file": "example2.py", "line": 20}
        ]
        self.mock_q.return_value = mock_results

        # Call the function
        result = untested_classes()

        # Verify the result
        self.assertEqual(result, mock_results)

        # Verify the query was called with the right parameters
        self.mock_q.assert_called_once()
        query_arg = self.mock_q.call_args[0][0]
        self.assertIn("WHERE NOT c:TestClass AND NOT (:TestClass)-[:TESTS]->(c)", query_arg)
        self.assertIn("AND NOT c.name STARTS WITH '_'", query_arg)

    def test_untested_classes_include_private(self):
        """Test the untested_classes tool with exclude_private=False."""
        # Set up mock return value
        mock_results = [
            {"name": "UntestClass", "file": "example.py", "line": 10},
            {"name": "_PrivateUntestClass", "file": "example.py", "line": 30}
        ]
        self.mock_q.return_value = mock_results

        # Call the function
        result = untested_classes(exclude_private=False)

        # Verify the result
        self.assertEqual(result, mock_results)

        # Verify the query was called with the right parameters
        self.mock_q.assert_called_once()
        query_arg = self.mock_q.call_args[0][0]
        self.assertIn("WHERE NOT c:TestClass AND NOT (:TestClass)-[:TESTS]->(c)", query_arg)
        self.assertNotIn("AND NOT c.name STARTS WITH '_'", query_arg)

    def test_transitive_calls(self):
        """Test the transitive_calls tool."""
        # Set up mock return value
        mock_results = [
            {
                "function_names": ["source_fn", "middle_fn", "target_fn"],
                "path_length": 2,
                "function_files": ["source.py", "middle.py", "target.py"]
            }
        ]
        self.mock_q_call_graph.return_value = mock_results

        # Call the function
        result = transitive_calls("source_fn", "target_fn")

        # Verify the result
        self.assertEqual(result, mock_results)

        # Verify the query was called with the right parameters
        self.mock_q_call_graph.assert_called_once()
        query_arg = self.mock_q_call_graph.call_args[0][0]
        self.assertIn("MATCH path = (source:Function {name: $source_fn})-[:CALLS*1..10]->(target:Function {name: $target_fn})", query_arg)

        # Check parameters
        kwargs = self.mock_q_call_graph.call_args[1]
        self.assertEqual(kwargs["source_fn"], "source_fn")
        self.assertEqual(kwargs["target_fn"], "target_fn")
        self.assertEqual(kwargs["max_depth"], 10)

    def test_transitive_calls_with_custom_depth(self):
        """Test the transitive_calls tool with a custom max_depth."""
        # Set up mock return value
        mock_results = [
            {
                "function_names": ["source_fn", "middle_fn", "target_fn"],
                "path_length": 2,
                "function_files": ["source.py", "middle.py", "target.py"]
            }
        ]
        self.mock_q_call_graph.return_value = mock_results

        # Call the function with custom max_depth
        result = transitive_calls("source_fn", "target_fn", max_depth=5)

        # Verify the result
        self.assertEqual(result, mock_results)

        # Verify the query was called with the right parameters
        self.mock_q_call_graph.assert_called_once()
        query_arg = self.mock_q_call_graph.call_args[0][0]
        self.assertIn("MATCH path = (source:Function {name: $source_fn})-[:CALLS*1..5]->(target:Function {name: $target_fn})", query_arg)

        # Check parameters
        kwargs = self.mock_q_call_graph.call_args[1]
        self.assertEqual(kwargs["max_depth"], 5)


if __name__ == "__main__":
    unittest.main()
