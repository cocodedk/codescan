#!/usr/bin/env bash
# Lint and test the way CI and graph-loop do: uv installs the locked
# dependencies into .venv, then ruff and pytest run against the local Neo4j
# on port 7600. Pass test paths to run only those; with none, the whole suite.
set -euo pipefail
cd "$(dirname "$0")/.."
if ! command -v uv >/dev/null; then
  echo "gate.sh: uv is not on PATH. Install it: https://docs.astral.sh/uv/getting-started/installation/" >&2
  echo "gate.sh: in graph-loop's sandbox, declare its path in the workspace's gate-paths.json." >&2
  exit 127
fi
uv sync --locked --quiet
uv run --locked ruff check .
export NEO4J_URI="${NEO4J_URI:-bolt://localhost:7600}" NEO4J_HOST="${NEO4J_HOST:-localhost}"
export NEO4J_PORT_BOLT="${NEO4J_PORT_BOLT:-7600}" NEO4J_USER="${NEO4J_USER:-neo4j}"
export NEO4J_PASSWORD="${NEO4J_PASSWORD:-strongpassword}"
exec uv run --locked pytest -q "$@"
