"""Helpers for the tests that scan small projects and read their import edges back."""
from codescan_lib.analysis import analyze_file, finalize_graph
from codescan_lib.db_operations import clear_database
from codescan_lib.mcp_tools.flow_tools import import_cycles
from codescan_lib.stats_collector import StatsCollector

MANY = 1000


def scan(session, tmp_path, files):
    """Scan a project given as {relative path: source}."""
    clear_database(session, quiet=True)
    stats = StatsCollector()
    for name, source in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source)
    for name in files:
        analyze_file(str(tmp_path / name), session, str(tmp_path), stats, defer_relationships=True)
    finalize_graph(session)


def edges(session):
    return sorted(
        (r["a"], r["b"]) for r in session.run(
            "MATCH (a:File)-[:IMPORTS_MODULE]->(b:File) RETURN a.path AS a, b.path AS b")
    )


def cycles():
    return [row["files"] for row in import_cycles(MANY)]
