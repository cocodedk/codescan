---
gate: bash scripts/gate.sh
---
# 07: the code follows CLAUDE.md's own rules

## What the owner wants

A standards review found code that breaks the repository's documented rules. Fix them without changing
what the scanner writes. Starts from `main` after every earlier spec is merged.

## What changes

- **No hardcoded strings** (CLAUDE.md): scope names (`module`, `class`, `function`), call kinds
  (`bare`, `self`, `attr`, and any added since), the receivers `self`/`cls`, TESTS methods
  (`naming_pattern`, `import`, `call`) and stats keys used outside `stats_collector.py` come from
  constants in `codescan_lib/constants.py`. Values stored in Neo4j stay plain strings, byte for byte.
- **Type annotations on every function** (CLAUDE.md) in `codescan_lib/`, `scanner.py` and
  `codescan_mcp_server.py`, including `session` parameters (`neo4j.Session` or `Any` where mocks are passed).
- **Docstrings on public functions and classes** (CONTRIBUTING.md) in `codescan_lib/`.
- **Files at or under 200 lines** (CLAUDE.md) across `codescan_lib/`, `scanner.py`,
  `codescan_mcp_server.py` and `tests/`, splitting by responsibility, not by line count.
- Stats are written through `StatsCollector` methods, not by assigning into its dicts from outside.

## Edges

- No behaviour change: on the same input the graph is identical (every node and edge, with labels and
  properties), and every MCP tool returns the same rows.
- Tests may be split across files; none may be deleted or weakened.

## Done when

1. The suite passes with at least as many tests as before.
2. A scan of a corpus (this repository plus another Python package) gives a graph identical to the one
   from `main` before the change: same sorted dump of every node and edge.
3. `ruff check .` passes; no file in the listed paths exceeds 200 lines.

## Out of scope

New features, renaming MCP tools, and changing stored values.
