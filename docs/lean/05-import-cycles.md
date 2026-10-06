---
gate: bash scripts/gate.sh tests/test_flow_import_cycles.py
---
# 05: find modules that import each other in a circle

## What the owner wants

Import cycles between a project's own modules tangle its flow and are a common thing to untangle first.
Today the scan records imports only for test files. Starts from `main` after spec 04 is merged.

## What changes

- **The scan records module imports for every file.** For each `import x` / `from x import y` whose module
  resolves to a file in the scanned project (absolute or relative, packages via `__init__.py`), the scan
  adds `(:File)-[:IMPORTS_MODULE {line}]->(:File)`. Imports of the standard library or third-party modules
  add nothing. Imports inside functions count; imports under `if TYPE_CHECKING:` do not.
- **A new MCP tool `import_cycles(limit: int = 20)`** returns each distinct cycle once, as `files` (the
  ordered list of file paths, starting at the alphabetically smallest) and `length`, shortest cycles first.
  A file importing itself is not a cycle.

## Edges

- The existing test-file `Import` nodes and their use for test links are unchanged.
- Rotations of the same cycle are reported once.

## Done when

The suite passes, and a new `tests/test_flow_import_cycles.py` proves (temporary projects, real Neo4j):

1. `a.py` imports `b`, `b.py` imports `a`: one cycle `[a.py, b.py]`.
2. A three-file cycle is reported once, starting at the smallest path.
3. Relative imports inside a package (`from . import b`, `from .b import f`) create edges.
4. `import os`, `import requests` and imports under `if TYPE_CHECKING:` create no edge.
5. A function-level import that closes a loop is reported.
6. The server's tool list includes `import_cycles`.
7. Every earlier test still passes. The builder may change any earlier test that pins the exact list of
   server tools, and nothing else in them.

## Out of scope

Breaking the cycles, cycles through third-party code, and package-level (directory) cycles.
