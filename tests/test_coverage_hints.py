"""Uncalled and untested lists say how many uncertain calls might reach each entry."""
import pytest
from neo4j import GraphDatabase

from codescan_lib.analysis import analyze_directory
from codescan_lib.constants import NEO4J_PASSWORD, NEO4J_URI, NEO4J_USER
from codescan_lib.db_operations import clear_database
from codescan_lib.mcp_tools.call_graph import uncalled_functions
from codescan_lib.mcp_tools.test_tools import untested_functions


@pytest.fixture
def session():
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    with driver.session() as s:
        yield s
    driver.close()


def scan(session, root, files: dict[str, str]) -> None:
    clear_database(session, quiet=True)
    for name, source in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source)
    analyze_directory(str(root), session)


def test_should_count_uncertain_calls_that_might_reach_an_uncalled_function(session, tmp_path):
    scan(session, tmp_path, {
        "m.py": "class Runner:\n    def run(self): pass\ndef fetch(session):\n    session.run()\n",
    })
    rows = {r["name"]: r["possible_callers"] for r in uncalled_functions()}
    assert rows["Runner.run"] == 1


def test_should_count_uncertain_test_calls_that_might_reach_an_untested_function(session, tmp_path):
    scan(session, tmp_path, {
        "m.py": "class Runner:\n    def run(self): pass\n",
        "tests/test_m.py": "def test_uses_runner(runner):\n    runner.run()\n",
    })
    rows = {r["name"]: r["possible_tests"] for r in untested_functions()}
    assert rows["Runner.run"] == 1
