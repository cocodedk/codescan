#!/bin/bash
# run_mcp_stdio_server.sh - Launch the CodeScan MCP stdio server
# Redirects all standard output to stderr to avoid interfering with JSON-RPC

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
cd "$SCRIPT_DIR" || exit 1

# uv installs the locked dependencies on first run; its messages go to stderr
exec uv run --project "$SCRIPT_DIR" --locked --quiet codescan-mcp
