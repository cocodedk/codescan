"""Connect tests to the production code they exercise: by name, by test class and by call.

A name that more than one definition carries links to none of them: a missing link is
acceptable, a false one is not.
"""
from collections import defaultdict
from typing import Any

from .constants import (
    COLOR_TESTS,
    TEST_CLASS_PATTERNS,
    TEST_FUNCTION_PREFIXES,
    TEST_METHOD_CALL,
    TEST_METHOD_NAMING,
)
from .graph_batch import LINKS, GraphBatch

Key = tuple[str, str, int]  # name, file, line: what identifies a node


def _by_simple_name(session: Any, label: str, exclude: str) -> dict[str, list[Key]]:
    """Production definitions of a kind, grouped by the name after the last dot."""
    found: dict[str, list[Key]] = defaultdict(list)
    for row in session.run(
        f"MATCH (n:{label}) WHERE NOT n:{exclude} AND coalesce(n.is_reference, false) = false "
        "RETURN n.name AS name, n.file AS file, n.line AS line"
    ):
        found[row["name"].rpartition(".")[2]].append((row["name"], row["file"], row["line"]))
    return found


def _name_starts(remainder: str) -> list[str]:
    """The remainder and each start of it that ends before an underscore, longest first."""
    cuts = [i for i, char in enumerate(remainder) if char == "_" and i > 0]
    return [remainder, *(remainder[:i] for i in reversed(cuts))]


def _prefix_remainder(simple_name: str, prefixes: list[str]) -> str:
    """What follows the test prefix, "" when the name has none."""
    return next((simple_name[len(p):] for p in prefixes if simple_name.startswith(p)), "")


def _link(test: Any, target: Key | None) -> list[dict[str, Any]]:
    """The row that writes a TESTS edge, when the test has one target and only one."""
    if target is None:
        return []
    return [{"test": test["name"], "test_file": test["file"], "test_line": test["line"],
             "name": target[0], "file": target[1], "line": target[2], "method": TEST_METHOD_NAMING}]


def _only(definitions: list[Key]) -> Key | None:
    return definitions[0] if len(definitions) == 1 else None


def function_links(session: Any, prefixes: list[str]) -> list[dict[str, Any]]:
    """Test functions paired with the one production function their name points at."""
    production = _by_simple_name(session, "Function", "TestFunction")
    links: list[dict[str, Any]] = []
    for test in session.run("MATCH (t:TestFunction) RETURN t.name AS name, t.file AS file, t.line AS line"):
        remainder = _prefix_remainder(test["name"].rpartition(".")[2], prefixes)
        longest = next((n for n in _name_starts(remainder) if n in production), "") if remainder else ""
        links += _link(test, _only(production[longest]) if longest else None)
    return links


def tested_class_name(test_class: str, patterns: list[str]) -> str:
    """The class a test class is named after by one of the `Test*` / `*Test` patterns, "" if none."""
    for pattern in patterns:
        head, star, tail = pattern.partition("*")
        stem = test_class[len(head):len(test_class) - len(tail)]
        if star and test_class.startswith(head) and test_class.endswith(tail) and stem:
            return stem
    return ""


def class_links(session: Any, patterns: list[str]) -> list[dict[str, Any]]:
    """Test classes paired with the one production class their name points at."""
    production = _by_simple_name(session, "Class", "TestClass")
    links: list[dict[str, Any]] = []
    for test in session.run("MATCH (t:TestClass) RETURN t.name AS name, t.file AS file, t.line AS line"):
        links += _link(test, _only(production.get(tested_class_name(test["name"], patterns), [])))
    return links


def _tests_query(test_label: str, tested_label: str) -> str:
    return f"""UNWIND $rows AS row
        MATCH (t:{test_label} {{name: row.test, file: row.test_file, line: row.test_line}})
        MATCH (p:{tested_label} {{name: row.name, file: row.file, line: row.line}})
        MERGE (t)-[:TESTS {{method: row.method, color: $color}}]->(p)"""


def link_tests(
    session: Any, function_prefixes: list[str] | None = None, class_patterns: list[str] | None = None
) -> None:
    """Connect test functions and test classes to the production code they exercise."""
    batch = GraphBatch("")
    for link in function_links(session, function_prefixes or TEST_FUNCTION_PREFIXES):
        batch.add(LINKS, _tests_query("TestFunction", "Function"), COLOR_TESTS, **link)
    for link in class_links(session, class_patterns or TEST_CLASS_PATTERNS):
        batch.add(LINKS, _tests_query("TestClass", "Class"), COLOR_TESTS, **link)
    batch.flush(session)
    session.run(
        """
        MATCH (test:TestFunction)-[:CALLS]->(prod:Function)
        WHERE NOT prod:TestFunction AND prod.is_reference = false
        MERGE (test)-[:TESTS {method: $method, color: $color}]->(prod)
        """,
        method=TEST_METHOD_CALL, color=COLOR_TESTS,
    )
