#!/usr/bin/env bash
# Lint and test the way graph-loop's sandbox runs the suite: a venv inside the
# tree (the host Python has no ensurepip) and the local Neo4j on port 7600.
# Pass test paths to run only those; with none, the whole suite runs.
set -euo pipefail
cd "$(dirname "$0")/.."
if [ ! -x .venv/bin/pip ]; then
  python3 -m venv --without-pip .venv
  curl -fsS https://bootstrap.pypa.io/get-pip.py | .venv/bin/python - -q
fi
.venv/bin/pip install -q -r requirements.txt ruff==0.16.8
.venv/bin/ruff check .
export NEO4J_URI="${NEO4J_URI:-bolt://localhost:7600}" NEO4J_HOST="${NEO4J_HOST:-localhost}"
export NEO4J_PORT_BOLT="${NEO4J_PORT_BOLT:-7600}" NEO4J_USER="${NEO4J_USER:-neo4j}"
export NEO4J_PASSWORD="${NEO4J_PASSWORD:-strongpassword}"
exec .venv/bin/python -m pytest -q "$@"
