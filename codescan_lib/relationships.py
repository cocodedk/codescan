"""Graph passes that need the whole project: call resolution and test linking.

They run after every file is analyzed, so the result does not depend on the
order files were visited in.
"""
from typing import Any

from .call_targets import NOT_NESTED, Definition, Position, choose_targets, module_of
from .constants import COLOR_CALLS, COLOR_TESTS, TEST_FUNCTION_PREFIXES


def resolve_calls(session: Any) -> None:
    """Re-point calls to placeholder nodes at the functions they certainly call."""
    index: dict[str, list[Definition]] = {}
    by_position: Position = {}
    for row in session.run("""
        MATCH (f:Function) WHERE f.is_reference = false
        RETURN f.name AS name, f.file AS file, f.line AS line, coalesce(f.parent_line, $none) AS parent_line
    """, none=NOT_NESTED):
        definition = Definition(row["name"], row["file"], row["line"], row["parent_line"])
        index.setdefault(row["name"].rpartition(".")[2], []).append(definition)
        by_position[(definition.file, definition.line)] = definition

    modules = {module_of(row["path"]) for row in session.run("MATCH (f:File) RETURN f.path AS path")}

    resolved = []
    for row in session.run("""
        MATCH (caller:Function {is_reference: false})-[r:CALLS]->(ref:ReferenceFunction)
        RETURN caller.name AS caller, caller.file AS caller_file, caller.line AS caller_line,
               ref.name AS callee, r.line AS line, r.args AS args, coalesce(r.kind, 'attr') AS kind,
               coalesce(r.recv_class, '') AS recv_class, coalesce(r.recv_module, '') AS recv_module
    """):
        caller = by_position[(row["caller_file"], row["caller_line"])]
        # A receiver that is a project module is never read as a class of the same name
        recv_class = "" if row["recv_module"] and row["recv_module"] in modules else row["recv_class"]
        targets = choose_targets(caller, row["callee"], index.get(row["callee"], []), by_position,
                                 row["kind"], recv_class, row["recv_module"])
        resolved += [{**row.data(), "target": t.name, "target_file": t.file, "target_line": t.line} for t in targets]

    if resolved:
        session.run(
            """
            UNWIND $rows AS row
            MATCH (caller:Function {name: row.caller, file: row.caller_file, line: row.caller_line, is_reference: false})
                  -[old:CALLS {line: row.line, args: row.args, kind: row.kind,
                                     recv_class: row.recv_class, recv_module: row.recv_module}]->(ref:ReferenceFunction {name: row.callee})
            MATCH (target:Function {name: row.target, file: row.target_file, line: row.target_line, is_reference: false})
            MERGE (caller)-[:CALLS {color: $color, line: row.line, args: row.args, kind: row.kind}]->(target)
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
