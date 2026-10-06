---
gate: bash scripts/gate.sh tests/test_flow_pass_through.py
---
# 03: find functions that only pass a call on

## What the owner wants

The owner wants CodeScan to show where a scanned codebase's flow can be simplified. The first and plainest
case is a function that does nothing but call one other function: a layer that can usually be cut, with
its callers calling the target directly. Starts from `main` after spec 02 is merged.

## What changes

- **The scan marks forwarders.** A defined function whose body, ignoring a leading docstring, is a single
  statement that is `return <call>` or a bare `<call>` gets `forwards_to` set to the called name on its
  node. Any other function has no `forwards_to`.
- **A new MCP tool `pass_through_functions`** returns one row per forwarder whose call resolved to a defined
  function: `name`, `file`, `line`, `target`, `target_file`, `callers` (how many functions call the
  forwarder) and `same_arguments` (true when the call passes exactly the forwarder's own parameters, in
  order, by name). Rows are ordered by `callers`, most first. Test functions, placeholders and dunder
  methods are left out.
- The tool lives in a new module under `codescan_lib/mcp_tools/` and is registered with the server like the
  other tools.

## Edges

- A forwarder whose call stayed unresolved is not listed.
- Decorated functions are listed; the decorator is not part of the body.
- `async def` functions and methods are handled like plain functions.

## Done when

The suite passes, and a new `tests/test_flow_pass_through.py` proves (temporary projects, real Neo4j, the
tool called directly):

1. `def a(x): return b(x)` with `def b(x): ...` is listed with target `b` and `same_arguments` true.
2. `def a(x): b(x, 1)` is listed with `same_arguments` false.
3. A function with a docstring and then `return b()` is listed; one with two statements is not.
4. A forwarder to an unresolved name is not listed; a test function forwarding is not listed.
5. `callers` counts the functions that call the forwarder, and rows are ordered by it.
6. The server's tool list includes `pass_through_functions`.
7. Every earlier test still passes. The builder may change any earlier test that pins the exact list of
   server tools, and nothing else in them.

## Out of scope

Rewriting the scanned code, wrappers that add a try/except or logging, and lambdas.
