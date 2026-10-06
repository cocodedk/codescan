---
gate: bash scripts/gate.sh tests/test_call_resolution.py
---
# 01: a CALLS edge means the call really reaches that function

## What the owner wants

CodeScan's graph is only useful for improving a codebase if its call edges are true. Two reviews of PR #56
found edges that are not: `session.run("x")` on a neo4j session becomes a call to the project's only
`Runner.run`, and a call to a nested `helper()` also links to another function's nested `helper` in the same
file. This spec starts from `main` after PR #56 is merged (`codescan_lib/relationships.py`,
`codescan_lib/call_names.py`, `tests/test_call_resolution.py` exist).

## What changes

- **Third-party receivers are skipped like the standard library.** A call whose receiver chain starts at a
  name bound by an import of a module that is neither standard library nor part of the scanned project
  (`import requests`, `from neo4j import GraphDatabase`, then `requests.get()`, `GraphDatabase.driver()`)
  records no call and no placeholder. A module is part of the project when its top-level name matches a
  top-level package or module in the scanned directory.
- **Unknown receivers stay unresolved.** An attribute call `x.name()` resolves to a project method only when
  the receiver is `self` or `cls`, a project class (`Foo.name()`), a name bound in the same function to a
  project class instance (`x = Foo()` then `x.name()`), or a project module alias (`utils.name()`). Any
  other receiver (a parameter, an attribute, a call result) keeps the call as an unresolved placeholder.
- **Nested definitions win for bare calls.** A bare `helper()` resolves first to a function defined directly
  inside the calling function, then to one in an enclosing function, then to a module-level function of the
  same file, then to a unique one elsewhere. A function nested in another function is never a target of a
  call made from outside its parent.
- **Targets are identified by line.** A resolved edge points at exactly one definition node (name, file and
  line); two same-named definitions in one file are never both targets of one call, except true repeated
  definitions at module level (overloads, `if`/`else` alternatives), which keep linking to all of them.
- **Resolved edges keep the call's `kind`** (`bare`, `self` or `attr`).

## Edges

- Every behaviour PR #56 added and its tests prove stays, unless this spec changes it above.
- Placeholders still act as nothing but call targets.
- No new node labels; `ReferenceFunction` stays the unresolved marker the MCP tools read.

## Done when

The suite passes, and new tests in `tests/test_call_resolution.py` prove (temporary projects, real Neo4j):

1. `def fetch(session): session.run("x")` beside `class Runner: def run(self)` leaves `fetch` unresolved.
2. `import requests` then `requests.get(u)` records no call; `from neo4j import GraphDatabase` then
   `GraphDatabase.driver(u)` records none.
3. `x = Runner()` then `x.run()` in one function resolves to `Runner.run`; `Runner.run()` does too.
4. With `import pkg.utils as utils` and `pkg/utils.py` defining `helper`, `utils.helper()` resolves to it.
5. `outer1` and `outer2` each nest a `helper`; each `helper()` call links only to its own parent's `helper`.
6. A module-level `helper` and a nested `helper` in one file: a call from a third function links only to the
   module-level one.
7. Two module-level `def f` in one file (overloads) both stay targets of `f()`.
8. A resolved edge carries the call's `kind`.
9. Every earlier test still passes. The builder may change earlier tests in `tests/test_call_resolution.py`
   that pin the old fallback for unknown receivers, and nothing else in them.

## Out of scope

Type inference beyond the same-function `x = Foo()` rule, inheritance (a call resolving to a base class's
method), calls to classes as constructors, and calls at module level.
