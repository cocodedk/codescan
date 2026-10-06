"""Tests for the find_class_relations MCP tool."""
import os
import sys
import unittest

# Add parent directory to path to import modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from mocked_queries import MockedQueries

from codescan_lib.mcp_tools.class_tools import find_class_relations


class TestClassRelations(MockedQueries):
    """Test the find_class_relations tool."""

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
