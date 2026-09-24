"""
Tests for the new CodeScan MCP tools:
- untested_classes
- transitive_calls
- find_function_relations
- find_class_relations
"""
import os
import sys
import unittest
from unittest.mock import MagicMock, patch

# Add parent directory to path to import modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import the tools we're testing
from codescan_lib.mcp_tools.call_graph import find_function_relations, transitive_calls
from codescan_lib.mcp_tools.class_tools import find_class_relations
from codescan_lib.mcp_tools.test_tools import untested_classes


class TestNewTools(unittest.TestCase):
    """Test the new tools added to the MCP server."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a mock for the Neo4j session and query results
        self.mock_session = MagicMock()
        self.mock_driver = MagicMock()
        self.mock_driver.session.return_value = self.mock_session

        # Patch the q function to use our mock
        self.q_patcher = patch('codescan_lib.mcp_tools.test_tools.q')
        self.mock_q = self.q_patcher.start()

        # Also patch q in call_graph module
        self.q_call_graph_patcher = patch('codescan_lib.mcp_tools.call_graph.q')
        self.mock_q_call_graph = self.q_call_graph_patcher.start()

        # Also patch q in class_tools module
        self.q_class_tools_patcher = patch('codescan_lib.mcp_tools.class_tools.q')
        self.mock_q_class_tools = self.q_class_tools_patcher.start()

    def tearDown(self):
        """Tear down test fixtures."""
        self.q_patcher.stop()
        self.q_call_graph_patcher.stop()
        self.q_class_tools_patcher.stop()

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

    def test_find_class_relations_exact_match(self):
        """Test the find_class_relations tool with exact matching."""
        # Set up mock return values for the queries
        # First query returns matching classes
        matching_classes = [
            {"name": "TestClass", "file": "example.py", "line": 10, "end_line": 50}
        ]

        # Second query returns methods
        methods = [
            {"method_name": "TestClass.method1", "method_line": 15, "method_end_line": 20, "method_length": 6},
            {"method_name": "TestClass.method2", "method_line": 25, "method_end_line": 30, "method_length": 6}
        ]

        # Third query returns file information
        file_info = [
            {"file_path": "example.py", "file_type": "production", "is_test_file": False, "is_example_file": False}
        ]

        # Fourth query returns related classes
        related_classes = [
            {"related_class_name": "RelatedClass", "related_class_file": "related.py", "shared_methods": 1}
        ]

        # Configure the mock to return different values for each call
        self.mock_q_class_tools.side_effect = [matching_classes, methods, file_info, related_classes]

        # Call the function
        result = find_class_relations("TestClass")

        # Verify the result structure
        self.assertEqual(len(result["matching_classes"]), 1)
        self.assertEqual(result["matching_classes"][0]["name"], "TestClass")
        self.assertEqual(len(result["relations"]), 1)
        self.assertEqual(result["relations"][0]["class"], matching_classes[0])
        self.assertEqual(result["relations"][0]["methods"], methods)
        self.assertEqual(result["relations"][0]["file"], file_info[0])
        self.assertEqual(result["relations"][0]["related_classes"], related_classes)

        # Verify the exact match query was used
        calls = self.mock_q_class_tools.call_args_list
        self.assertEqual(len(calls), 4)

        # Check first query (find matching classes)
        first_query = calls[0][0][0]
        self.assertIn("MATCH (c:Class {name: $name})", first_query)
        self.assertEqual(calls[0][1]["name"], "TestClass")

        # Check second query (methods)
        second_query = calls[1][0][0]
        self.assertIn("MATCH (c:Class {name: $name, file: $file})-[:CONTAINS]->(f:Function)", second_query)

        # Check third query (file info)
        third_query = calls[2][0][0]
        self.assertIn("MATCH (f:File)-[:CONTAINS]->(c:Class {name: $name, file: $file})", third_query)

        # Check fourth query (related classes)
        fourth_query = calls[3][0][0]
        self.assertIn("MATCH (c:Class {name: $name, file: $file})-[:CONTAINS]->(f:Function)", fourth_query)
        self.assertIn("MATCH (other:Class)-[:CONTAINS]->(of:Function)", fourth_query)

    def test_find_class_relations_partial_match(self):
        """Test the find_class_relations tool with partial matching."""
        # Set up mock return values
        matching_classes = [
            {"name": "TestClass", "file": "example1.py", "line": 10, "end_line": 50},
            {"name": "AnotherTestClass", "file": "example2.py", "line": 60, "end_line": 100}
        ]

        # Return empty lists for methods and related classes to keep test simple
        empty_methods = []
        empty_related = []
        file_info_1 = [{"file_path": "example1.py", "file_type": "production", "is_test_file": False, "is_example_file": False}]
        file_info_2 = [{"file_path": "example2.py", "file_type": "production", "is_test_file": False, "is_example_file": False}]

        # Configure mock to return different values for each call
        self.mock_q_class_tools.side_effect = [
            matching_classes,  # First query for matching classes
            empty_methods, file_info_1, empty_related,  # Queries for first class
            empty_methods, file_info_2, empty_related   # Queries for second class
        ]

        # Call the function with partial matching
        result = find_class_relations("Test", partial_match=True)

        # Verify the result structure
        self.assertEqual(len(result["matching_classes"]), 2)
        self.assertEqual(result["matching_classes"][0]["name"], "TestClass")
        self.assertEqual(result["matching_classes"][1]["name"], "AnotherTestClass")

        # Verify the partial match query was used
        calls = self.mock_q_class_tools.call_args_list
        self.assertEqual(len(calls), 7)  # 1 for finding classes + 3 per class for relations

        # Check first query (find matching classes)
        first_query = calls[0][0][0]
        self.assertIn("WHERE c.name CONTAINS $name", first_query)
        self.assertEqual(calls[0][1]["name"], "Test")

    def test_find_class_relations_no_matches(self):
        """Test the find_class_relations tool with no matching classes."""
        # Set up mock to return empty list for the first query
        self.mock_q_class_tools.return_value = []

        # Call the function
        result = find_class_relations("NonexistentClass")

        # Verify the result structure
        self.assertEqual(result["matching_classes"], [])
        self.assertEqual(result["relations"], [])

        # Verify only one query was made (since we return early when no matches)
        self.mock_q_class_tools.assert_called_once()

if __name__ == "__main__":
    unittest.main()
