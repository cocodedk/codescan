# Profile: CodeScan, a Python analyzer tested against Neo4j

The lean loop reads the first indented line under each heading below.

## suite_command

    bash scripts/gate.sh

Builds a venv inside the worktree, installs `requirements.txt` and CI's ruff pin, runs `ruff check .`,
then `pytest` against the Neo4j on `bolt://localhost:7600` (user `neo4j`, password `strongpassword`).
That Neo4j must be running: the container `codescan-neo4j-dev` (image `neo4j:5.26.0`, restart policy
`unless-stopped`). The suite clears its database. The sandbox keeps the network, so pip can download.

## build_command

    bash scripts/gate.sh

There is no build step. The build is the suite, run on the pull request's branch.

## artifact

    README.md

A library and MCP server: the README says how to scan a project and connect the tools.

## account

    REPLACE-WITH-ACCOUNT-NAME
