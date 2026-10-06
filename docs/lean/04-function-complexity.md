---
gate: bash scripts/gate.sh tests/test_flow_complexity.py
---
# 04: rank functions by how many paths run through them

## What the owner wants

To find where flow can be simplified, the owner needs to see which functions branch the most. Length alone
(already stored) misses a short function full of nested conditions. Starts from `main` after spec 03 is
merged.

## What changes

- **The scan stores `complexity` on every defined function**: 1, plus 1 for each of these branch points:
  `if`/`elif`, `for`/`async for`,
  `while`, each `except` handler, each `case` of a `match`, each conditional expression (`a if c else b`),
  each `if` inside a comprehension, and each extra operand of `and`/`or` (`a and b and c` adds 2). Branches
  inside a nested function or class count toward that nested definition, not its parent.
- **The scan stores `max_nesting`**: the deepest level of nested `if`/`for`/`while`/`try`/`with`/`match`
  blocks in the function's own body (0 for a flat body).
- **A new MCP tool `most_complex_functions(limit: int = 20)`** returns `name`, `file`, `line`, `length`,
  `complexity` and `max_nesting` for defined, non-test functions, ordered by `complexity` then
  `max_nesting`, highest first.

## Edges

- Placeholders have neither property and are never listed.
- The tool sits in the same module as spec 03's tool.

## Done when

The suite passes, and a new `tests/test_flow_complexity.py` proves (temporary projects, real Neo4j):

1. A function with no branches has complexity 1 and nesting 0.
2. `if`/`elif`/`else` adds 2; a `for` with an `if` inside gives complexity 3 and nesting 2.
3. `a and b and c` adds 2; `x if c else y` adds 1; `[v for v in xs if v]` adds 1; each `except` adds 1;
   each `case` adds 1.
4. A nested function's branches do not count toward its parent.
5. `most_complex_functions` orders by complexity, then nesting, respects `limit`, and leaves out tests.
6. The server's tool list includes `most_complex_functions`.
7. Every earlier test still passes. The builder may change any earlier test that pins the exact list of
   server tools, and nothing else in them.

## Out of scope

Thresholds or warnings, cognitive-complexity weighting, and per-file totals.
