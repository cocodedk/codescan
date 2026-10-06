"""Graph passes that need the whole project: call resolution and test linking.

They run after every file is analyzed, so the result does not depend on the
order files were visited in.
"""
from typing import Any, NamedTuple

from .constants import COLOR_CALLS, COLOR_TESTS, TEST_FUNCTION_PREFIXES

BARE_CALL, SELF_CALL, ATTR_CALL = "bare", "self", "attr"


class Definition(NamedTuple):
    name: str
    file: str


def choose_target(
    caller: str, caller_file: str, callee: str, candidates: list[Definition], kind: str = ATTR_CALL
) -> Definition | None:
    """Pick the one definition a call most plausibly refers to, or None if unclear.

    The call's shape decides which definitions it can reach. A bare `name()` can
    only reach plain functions. `self.name()` reaches methods, the caller's own
    class first. `other.name()` reaches methods or, as `module.name()`, plain
    functions, but never the calling function itself. Within that, the closest
    definition wins (same file before anywhere), and a tier holding several
    matches is ambiguous, so the call stays unresolved.
    """
    def is_method(d: Definition) -> bool:
        return d.name != callee

    owner = caller.rpartition(".")[0]
    if kind == BARE_CALL:
        tiers = [lambda d: d.file == caller_file, lambda d: True]
        candidates = [d for d in candidates if not is_method(d)]
    else:
        tiers = [lambda d: is_method(d) and d.file == caller_file, is_method]
        if kind == SELF_CALL:
            tiers.insert(0, lambda d: bool(owner) and d.name == f"{owner}.{callee}" and d.file == caller_file)
        else:
            tiers.append(lambda d: not is_method(d))
            candidates = [d for d in candidates if d != Definition(caller, caller_file)]
    for tier in tiers:
        matches = [d for d in candidates if tier(d)]
        if matches:
            return matches[0] if len(matches) == 1 else None
    return None


def resolve_calls(session: Any) -> None:
    """Re-point calls to placeholder nodes at the function they actually call."""
    index: dict[str, set[Definition]] = {}
    for row in session.run(
        "MATCH (f:Function) WHERE f.is_reference = false RETURN f.name AS name, f.file AS file"
    ):
        index.setdefault(row["name"].rpartition(".")[2], set()).add(Definition(row["name"], row["file"]))

    resolved = []
    for row in session.run("""
        MATCH (caller:Function {is_reference: false})-[r:CALLS]->(ref:ReferenceFunction)
        RETURN caller.name AS caller, caller.file AS caller_file, caller.line AS caller_line,
               ref.name AS callee, r.line AS line, r.args AS args, coalesce(r.kind, 'attr') AS kind
    """):
        candidates = sorted(index.get(row["callee"], ()))
        target = choose_target(row["caller"], row["caller_file"], row["callee"], candidates, row["kind"])
        if target:
            resolved.append({**row.data(), "target": target.name, "target_file": target.file})

    if resolved:
        session.run(
            """
            UNWIND $rows AS row
            MATCH (caller:Function {name: row.caller, file: row.caller_file, line: row.caller_line, is_reference: false})
                  -[old:CALLS {line: row.line, args: row.args, kind: row.kind}]->(ref:ReferenceFunction {name: row.callee})
            MATCH (target:Function {name: row.target, file: row.target_file, is_reference: false})
            MERGE (caller)-[:CALLS {color: $color, line: row.line, args: row.args}]->(target)
            DELETE old
            """,
            rows=resolved,
            color=COLOR_CALLS,
        )
    session.run("MATCH (ref:ReferenceFunction) WHERE NOT ()-[:CALLS]->(ref) DETACH DELETE ref")


def count_unresolved(session: Any) -> int:
    """Number of callee names no definition could be found for."""
    return int(session.run("MATCH (ref:ReferenceFunction) RETURN count(ref) AS n").single()["n"])


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
