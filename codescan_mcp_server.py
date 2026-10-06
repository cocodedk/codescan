#!/usr/bin/env python3
"""
codescan_mcp_server.py - MCP Server using MCPServer and stdio.
Provides tools to query a Neo4j database populated with code analysis data.
"""
from codescan_lib.mcp_tools.base import driver, initial_connection_status, logger, mcp
from codescan_lib.mcp_tools.call_graph import *
from codescan_lib.mcp_tools.class_tools import *
from codescan_lib.mcp_tools.constant_tools import *
from codescan_lib.mcp_tools.core import *
from codescan_lib.mcp_tools.file_tools import *
from codescan_lib.mcp_tools.flow_tools import *
from codescan_lib.mcp_tools.test_tools import *

# Tools are listed in the order they register: the coverage tools come after test_tools
# isort: split
from codescan_lib.mcp_tools.test_coverage_tools import *


def main() -> None:
    """Serve the CodeScan tools over stdio until the client disconnects."""
    logger.info("Starting CodeScan MCP Server (MCPServer, stdio)")
    logger.info(f"Database connection status: {'Success' if initial_connection_status['success'] else 'Failed'}")
    if not initial_connection_status['success']:
        logger.warning(f"Connection details: URI={initial_connection_status['uri']}, USER={initial_connection_status['user']}, PORT={initial_connection_status['port']}")
        logger.error(f"Connection error: {initial_connection_status['error']}")

    try:
        mcp.run(transport='stdio')
    except Exception as e:  # noqa: BLE001 -- top-level guard: log and close the driver instead of a bare crash
        logger.error(f"Server crashed: {e}", exc_info=True)
    finally:
        if driver:
            driver.close()
            logger.info("Neo4j driver closed")


if __name__ == "__main__":
    main()
