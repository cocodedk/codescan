---
gate: bash scripts/gate.sh tests/test_call_resolution.py
---
# 06: calls to classes and calls at module level are recorded

## What the owner wants

Two kinds of call never reach the graph, so the graph misreports flow. `Foo()` on a project class
records nothing true: it becomes an unresolved placeholder named `Foo`. A call at module level, outside
any function (`if __name__ == "__main__": main()`, module setup), records nothing, so `main` and other
entry points show up in `uncalled_functions` as dead code. Starts from `main` after spec 02 is merged.

## What changes

- **Constructor calls link to the class.** After the scan, a call whose callee name resolves to a project
  class (same file first, then a unique class anywhere; bare `Foo()` or `module.Foo()`) is stored as
  `(caller)-[:INSTANTIATES {line, args}]->(:Class)` instead of a CALLS edge to a placeholder. A name that
  matches no class keeps today's behaviour.
- **Module-level calls have the file as caller.** A call made outside any function or class body is
  recorded with the file's `File` node as caller, resolved exactly like a function's call
  (`(:File)-[:CALLS {line, args, kind}]->(:Function)`), and the same for constructor calls
  (`(:File)-[:INSTANTIATES]->(:Class)`). Calls in a class body outside methods also count as the file's.
- **`uncalled_functions` counts these.** A function called only from module level is no longer listed.
  Other tools that read CALLS keep working; where a tool returns a caller name, a File caller is returned
  as its path.

## Edges

- Decorator calls at module level (`@app.route("/")`) are module-level calls of the file.
- Placeholders still act only as call targets; resolution rules of specs 01 and 02 apply unchanged.
- The graph for code without constructor or module-level calls is unchanged.

## Done when

The suite passes, and new tests in `tests/test_call_resolution.py` prove (temporary projects, real Neo4j):

1. `def f(): Foo()` with `class Foo` in another file gives `f -[:INSTANTIATES]-> Foo` and no placeholder `Foo`.
2. `Foo()` where no class `Foo` exists stays an unresolved placeholder.
3. `if __name__ == "__main__": main()` gives `File(m.py) -[:CALLS]-> main`, and `uncalled_functions` does not list `main`.
4. A module-level `x = helper()` gives `File -[:CALLS]-> helper`.
5. A module-level `Foo()` gives `File -[:INSTANTIATES]-> Foo`.
6. Every earlier test still passes. The builder may change earlier tests that assert a placeholder named
   after a project class, and nothing else in them.

## Out of scope

Inheritance, calls through `super()`, metaclasses, and instance tracking beyond spec 01's rule.
