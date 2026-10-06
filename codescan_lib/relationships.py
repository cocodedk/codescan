"""Graph passes that need the whole project: call resolution and test linking.

They run after every file is analyzed, so the result does not depend on the
order files were visited in.
"""
from typing import Any, NamedTuple

from .constants import COLOR_CALLS, COLOR_TESTS, TEST_FUNCTION_PREFIXES


class Definition(NamedTuple):
    name: str
    file: str


def choose_target(
    caller: str, caller_file: str, callee: str, candidates: list[Definition], bare: bool = False
) -> Definition | None:
    """Pick the one definition a call most plausibly refers to, or None if unclear.

    Tiers, most specific first: a method of the caller's own class, a function
    of that name in the caller's file, any definition in the caller's file, a
    function of that name anywhere, then any definition. A tier with several
    matches is ambiguous, so the call stays unresolved. A bare `name()` call
    cannot reach a method, so only plain functions are candidates for it.
    """
    if bare:
        candidates = [d for d in candidates if d.name == callee]
    owner = caller.rpartition(".")[0]
    tiers = (
        lambda d: bool(owner) and d.name == f"{owner}.{callee}" and d.file == caller_file,
        lambda d: d.name == callee and d.file == caller_file,
        lambda d: d.file == caller_file,
        lambda d: d.name == callee,
        lambda d: True,
    )
    for tier in tiers:
        matches = [d for d in candidates if tier(d)]
        if matches:
            return matches[0] if len(matches) == 1 else None
    return None


def resolve_calls(session: Any) -> None:
    """Re-point calls to placeholder nodes at the function they actually call."""
    index: dict[str, list[Definition]] = {}
    for row in session.run(
        "MATCH (f:Function) WHERE f.is_reference = false RETURN f.name AS name, f.file AS file"
    ):
        index.setdefault(row["name"].rpartition(".")[2], []).append(Definition(row["name"], row["file"]))

    resolved = []
    for row in session.run("""
        MATCH (caller:Function)-[r:CALLS]->(ref:ReferenceFunction)
        RETURN caller.name AS caller, caller.file AS caller_file, ref.name AS callee,
               r.line AS line, r.args AS args, coalesce(r.bare, false) AS bare
    """):
        candidates = index.get(row["callee"], [])
        target = choose_target(row["caller"], row["caller_file"], row["callee"], candidates, row["bare"])
        if target:
            resolved.append({**row.data(), "target": target.name, "target_file": target.file})

    if resolved:
        session.run(
            """
            UNWIND $rows AS row
            MATCH (caller:Function {name: row.caller, file: row.caller_file})
                  -[old:CALLS {line: row.line}]->(ref:ReferenceFunction {name: row.callee})
            MATCH (target:Function {name: row.target, file: row.target_file, is_reference: false})
            MERGE (caller)-[:CALLS {color: $color, line: row.line, args: row.args}]->(target)
            DELETE old
            """,
            rows=resolved,
            color=COLOR_CALLS,
        )
    session.run("MATCH (ref:ReferenceFunction) WHERE NOT ()-[:CALLS]->(ref) DETACH DELETE ref")


def link_tests(session: Any, function_prefixes: list[str] | None = None) -> None:
    """Connect test functions to the production functions they exercise."""
    for prefix in function_prefixes or TEST_FUNCTION_PREFIXES:
        session.run(
            """
            MATCH (test:TestFunction)
            WHERE test.name STARTS WITH $prefix
            WITH test, substring(test.name, $prefix_len) AS tested_name
            MATCH (prod:Function)
            WHERE NOT prod:TestFunction AND prod.is_reference = false
              AND (prod.name = tested_name OR prod.name ENDS WITH ('.' + tested_name))
            MERGE (test)-[:TESTS {method: 'naming_pattern', color: $edge_color}]->(prod)
            """,
            prefix=prefix,
            prefix_len=len(prefix),
            edge_color=COLOR_TESTS,
        )
    session.run(
        """
        MATCH (test:TestFunction)-[:IMPORTS]->(i:Import)
        MATCH (prod:Function)
        WHERE NOT prod:TestFunction AND prod.is_reference = false AND prod.name = i.name
        MERGE (test)-[:TESTS {method: 'import', color: $edge_color}]->(prod)
        """,
        edge_color=COLOR_TESTS,
    )
    session.run(
        """
        MATCH (test:TestFunction)-[:CALLS]->(prod:Function)
        WHERE NOT prod:TestFunction AND prod.is_reference = false
        MERGE (test)-[:TESTS {method: 'call', color: $edge_color}]->(prod)
        """,
        edge_color=COLOR_TESTS,
    )
