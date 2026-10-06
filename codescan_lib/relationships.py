"""Graph pass that needs the whole project: call resolution.

It runs after every file is analyzed, so the result does not depend on the
order files were visited in.
"""
from typing import Any

from .call_targets import (
    NOT_NESTED,
    Definition,
    Position,
    build_exporters,
    choose_targets,
    module_of,
    module_scope,
)
from .class_targets import ClassDefinition, class_targets
from .constants import COLOR_CALLS
from .graph_batch import LINKS, GraphBatch

# A call edge is found by its own id, so a function caller and a file caller (module-level code) share the rewrite
REWRITE_CALLS = """UNWIND $rows AS row
    MATCH (caller) WHERE elementId(caller) = row.caller_id
    MATCH ()-[old:CALLS]->() WHERE elementId(old) = row.edge_id
    MATCH (target:Function {name: row.target, file: row.target_file, line: row.target_line, is_reference: false})
    MERGE (caller)-[:CALLS {color: $color, line: row.line, args: row.args, kind: row.kind}]->(target)
    DELETE old"""
REWRITE_INSTANTIATES = """UNWIND $rows AS row
    MATCH (caller) WHERE elementId(caller) = row.caller_id
    MATCH ()-[old:CALLS]->() WHERE elementId(old) = row.edge_id
    MATCH (target:Class {name: row.target, file: row.target_file, line: row.target_line})
    MERGE (caller)-[:INSTANTIATES {color: $color, line: row.line, args: row.args}]->(target)
    DELETE old"""


def resolve_calls(session: Any) -> None:
    """Re-point calls to placeholder nodes at the functions they certainly call, or at the class they certainly build.

    A call outside every function has the file as caller."""
    index: dict[str, list[Definition]] = {}
    by_position: Position = {}
    for row in session.run("""
        MATCH (f:Function) WHERE f.is_reference = false
        RETURN f.name AS name, f.file AS file, f.line AS line, coalesce(f.parent_line, $none) AS parent_line
    """, none=NOT_NESTED):
        definition = Definition(row["name"], row["file"], row["line"], row["parent_line"])
        index.setdefault(row["name"].rpartition(".")[2], []).append(definition)
        by_position[(definition.file, definition.line)] = definition

    classes: dict[str, list[ClassDefinition]] = {}
    for row in session.run("MATCH (c:Class) RETURN c.name AS name, c.file AS file, c.line AS line, "
                           "coalesce(c.nested, false) AS nested"):
        classes.setdefault(row["name"], []).append(ClassDefinition(row["name"], row["file"], row["line"], row["nested"]))

    files = [(row["path"], row["exports"]) for row in session.run(
        "MATCH (f:File) RETURN f.path AS path, coalesce(f.exports, []) AS exports")]
    modules = {module_of(path) for path, _ in files}
    exporters = build_exporters(files)

    batch = GraphBatch("")
    for row in session.run("""
        MATCH (caller)-[r:CALLS]->(ref:ReferenceFunction) WHERE caller:File OR caller.is_reference = false
        RETURN elementId(caller) AS caller_id, elementId(r) AS edge_id, ref.name AS callee,
               coalesce(caller.file, caller.path) AS caller_file, caller.line AS caller_line,
               r.line AS line, r.args AS args, coalesce(r.kind, 'attr') AS kind,
               coalesce(r.recv_class, '') AS recv_class, coalesce(r.recv_module, '') AS recv_module
    """):
        caller = by_position[(row["caller_file"], row["caller_line"])] if row["caller_line"] else module_scope(row["caller_file"])
        # A receiver that is a project module is never read as a class of the same name
        recv_class = "" if row["recv_module"] and row["recv_module"] in modules else row["recv_class"]
        functions = choose_targets(caller, row["callee"], index.get(row["callee"], []), by_position,
                                   row["kind"], recv_class, row["recv_module"], exporters)
        built = class_targets(caller.file, row["callee"], classes.get(row["callee"], []), row["kind"],
                              row["recv_module"], exporters)
        if functions and built:  # a function and a class could both be meant: neither is certain
            continue
        fields = {k: row[k] for k in ("caller_id", "edge_id", "line", "args", "kind")}
        for query, targets in ((REWRITE_CALLS, functions), (REWRITE_INSTANTIATES, built)):
            for t in targets:
                batch.add(LINKS, query, COLOR_CALLS, **fields, target=t.name, target_file=t.file, target_line=t.line)
    batch.flush(session)
    session.run("MATCH (ref:ReferenceFunction) WHERE NOT ()-[:CALLS]->(ref) DETACH DELETE ref")


def count_unresolved(session: Any) -> int:
    """Number of callee names no definition could be found for."""
    return int(session.run("MATCH (ref:ReferenceFunction) RETURN count(ref) AS n").single()["n"])
