"""Helpers for the tests that scan small projects and read the call graph back."""
from codescan_lib.analysis import analyze_file, finalize_graph
from codescan_lib.db_operations import clear_database
from codescan_lib.stats_collector import StatsCollector


def scan(session, root, files, order=None):
    """Write files, analyze them in the given order, then finalize the graph."""
    stats = StatsCollector()
    clear_database(session, quiet=True)
    for name, source in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source)
    for name in order or list(files):
        analyze_file(str(root / name), session, str(root), stats, defer_relationships=True)
    finalize_graph(session)
    return stats


def rows(session, query):
    return {tuple(r.values()) for r in session.run(query)}


def resolved_calls(session):
    return rows(session, """
        MATCH (a:Function)-[:CALLS]->(b:Function)
        WHERE b.is_reference = false RETURN a.name, b.name""")


def unresolved_calls(session):
    return rows(session, """
        MATCH (a:Function)-[:CALLS]->(b:ReferenceFunction) RETURN a.name, b.name""")


RUNNER = "class Runner:\n    def run(self): pass\n"


R_RUN = "class R:\n    def run(self): pass\n"


def instantiated(session):
    return rows(session, "MATCH (a)-[:INSTANTIATES]->(c:Class) RETURN coalesce(a.name, a.path), c.name, c.file")


def module_calls(session):
    return rows(session, "MATCH (a:File)-[:CALLS]->(b:Function {is_reference: false}) RETURN a.path, b.name")


FOO = "class Foo: pass\n"
