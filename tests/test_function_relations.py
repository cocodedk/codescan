"""Tests for the find_function_relations MCP tool."""
import os
import sys
import unittest

# Add parent directory to path to import modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from mocked_queries import MockedQueries

from codescan_lib.mcp_tools.call_graph import find_function_relations


class TestFunctionRelations(MockedQueries):
    """Test the find_function_relations tool."""

    def test_find_function_relations_exact_match(self):
        """Test the find_function_relations tool with exact matching."""
        # Set up mock return values for the three queries
        # First query returns matching functions
        matching_functions = [
            {"name": "target_function", "file": "example.py", "line": 10, "end_line": 20}
        ]

        # Second query returns callers
        callers = [
            {"caller_name": "caller_function", "caller_file": "caller.py"}
        ]

        # Third query returns callees
        callees = [
            {"callee_name": "callee_function", "callee_file": "callee.py"}
        ]

        # Configure the mock to return different values for each call
        self.mock_q_call_graph.side_effect = [matching_functions, callers, callees]

        # Call the function
        result = find_function_relations("target_function")

        # Verify the result structure
        self.assertEqual(len(result["matching_functions"]), 1)
        self.assertEqual(result["matching_functions"][0]["name"], "target_function")
        self.assertEqual(len(result["relations"]), 1)
        self.assertEqual(result["relations"][0]["function"], matching_functions[0])
        self.assertEqual(result["relations"][0]["callers"], callers)
        self.assertEqual(result["relations"][0]["callees"], callees)

        # Verify the exact match query was used
        calls = self.mock_q_call_graph.call_args_list
        self.assertEqual(len(calls), 3)

        # Check first query (find matching functions)
        first_query = calls[0][0][0]
        self.assertIn("MATCH (f:Function {name: $name})", first_query)
        self.assertEqual(calls[0][1]["name"], "target_function")

        # Check second query (callers)
        second_query = calls[1][0][0]
        self.assertIn("MATCH (caller:Function)-[:CALLS]->(f:Function {name: $name})", second_query)

        # Check third query (callees)
        third_query = calls[2][0][0]
        self.assertIn("MATCH (f:Function {name: $name})-[:CALLS]->(callee:Function)", third_query)

    def test_find_function_relations_partial_match(self):
        """Test the find_function_relations tool with partial matching."""
        # Set up mock return values
        matching_functions = [
            {"name": "contains_target", "file": "example1.py", "line": 10, "end_line": 20},
            {"name": "target_in_middle", "file": "example2.py", "line": 30, "end_line": 40}
        ]

        # Return empty lists for callers and callees to keep test simple
        empty_list = []

        # Configure mock to return different values for each call (3 calls per function)
        self.mock_q_call_graph.side_effect = [
            matching_functions,  # First query for matching functions
            empty_list, empty_list,  # Callers and callees for first function
            empty_list, empty_list   # Callers and callees for second function
        ]

        # Call the function with partial matching
        result = find_function_relations("target", partial_match=True)

        # Verify the result structure
        self.assertEqual(len(result["matching_functions"]), 2)
        self.assertEqual(result["matching_functions"][0]["name"], "contains_target")
        self.assertEqual(result["matching_functions"][1]["name"], "target_in_middle")

        # Verify the partial match query was used
        calls = self.mock_q_call_graph.call_args_list
        self.assertEqual(len(calls), 5)  # 1 for finding functions + 2 per function for relations

        # Check first query (find matching functions)
        first_query = calls[0][0][0]
        self.assertIn("WHERE f.name CONTAINS $name", first_query)
        self.assertEqual(calls[0][1]["name"], "target")

    def test_find_function_relations_no_matches(self):
        """Test the find_function_relations tool with no matching functions."""
        # Set up mock to return empty list for the first query
        self.mock_q_call_graph.return_value = []

        # Call the function
        result = find_function_relations("nonexistent_function")

        # Verify the result structure
        self.assertEqual(result["matching_functions"], [])
        self.assertEqual(result["relations"], [])

        # Verify only one query was made (since we return early when no matches)
        self.mock_q_call_graph.assert_called_once()


if __name__ == "__main__":
    unittest.main()
