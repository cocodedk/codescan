"""A TestCase that stands a mock in for the Cypher runner of every tool module under test."""
import unittest
from unittest.mock import MagicMock, patch


class MockedQueries(unittest.TestCase):
    """Replaces `q` in the coverage, call graph and class tools, so a tool runs without Neo4j."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a mock for the Neo4j session and query results
        self.mock_session = MagicMock()
        self.mock_driver = MagicMock()
        self.mock_driver.session.return_value = self.mock_session

        # Patch the q function to use our mock
        self.q_patcher = patch('codescan_lib.mcp_tools.test_coverage_tools.q')
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
