---
gate: bash scripts/gate.sh tests/test_test_links.py
---
# 02: tests link to the code they test, the way the docs promise

## What the owner wants

`docs/test_coverage_detection.md` promises that tests link to production code by naming, by imports and by
calls, and that test classes link to the classes they test. A review of PR #56 found three of these missing:
unittest methods never match by name, `test_compute_doubles` does not match `compute`, and test classes
link to nothing. The coverage tools (`untested_functions`, `get_test_coverage_ratio`) are only as good as
these links. Starts from `main` after spec 01 is merged.

## What changes

- **Test methods match by name.** For a test method `TestCompute.test_compute`, the part after the class
  (`test_compute`) is matched like a test function.
- **Name prefixes match.** After the test prefix is removed, the remainder matches a production function or
  method whose simple name equals it, or equals its start followed by `_` (`test_compute_doubles` matches
  `compute`; the longest such name wins, so `compute_all` beats `compute` for `test_compute_all_x`).
- **Test classes link to classes.** A test class whose name is a production class name with a configured
  test class pattern applied (`TestFoo`, `FooTest` for `Foo`, from `TEST_CLASS_PATTERNS`) gets a
  `TESTS {method: 'naming_pattern'}` edge to that class.
- **Test files' imports resolve their calls.** When a test calls a name it imported
  (`from pkg.a import compute` then `compute()`), the call resolves to the definition in that module even if
  another module defines the same name. A name that is imported but never called does not count as tested.

## Edges

- A production function counts as tested only through a real call, a name match or a test class link; an
  import alone never does.
- Placeholders are never tested and never counted by the coverage tools.

## Done when

The suite passes, and a new `tests/test_test_links.py` proves (temporary projects, real Neo4j):

1. `class TestCompute(unittest.TestCase): def test_compute(self)` links to `compute`.
2. `test_compute_doubles` links to `compute`; `test_compute_all_x` links to `compute_all`, not `compute`.
3. `class TestFoo` and `class FooTest` each link to `class Foo`.
4. With `compute` defined in `pkg/a.py` and `pkg/b.py`, a test doing `from pkg.a import compute; compute()`
   links to the one in `pkg/a.py` only.
5. A test file that imports `helper` but never calls it gives `helper` no TESTS edge.
6. `get_test_coverage_ratio` counts only defined, non-test functions.
7. Every earlier test still passes.

## Out of scope

Coverage from running the tests, parametrized test ids, and fixtures as tested code.
