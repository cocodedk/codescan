"""pass_through_functions lists functions whose whole body is one call to another defined function."""
import asyncio

import pytest
from neo4j import GraphDatabase

from codescan_lib.analysis import analyze_file, finalize_graph
from codescan_lib.constants import NEO4J_PASSWORD, NEO4J_URI, NEO4J_USER
from codescan_lib.db_operations import clear_database
from codescan_lib.mcp_tools.flow_tools import pass_through_functions
from codescan_lib.stats_collector import StatsCollector

FORWARD = "def a(x):\n    return b(x)\n\ndef b(x):\n    return x\n"


@pytest.fixture
def session():
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    with driver.session() as s:
        yield s
    driver.close()


def listed(session, tmp_path, source, name="m.py"):
    """Scan one file and return the tool's rows keyed by function name."""
    stats = StatsCollector()
    clear_database(session, quiet=True)
    path = tmp_path / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source)
    analyze_file(str(path), session, str(tmp_path), stats, defer_relationships=True)
    finalize_graph(session)
    return {row["name"]: row for row in pass_through_functions()}


def test_should_list_a_forwarder_passing_its_own_parameters(session, tmp_path):
    rows = listed(session, tmp_path, FORWARD)
    assert (rows["a"]["target"], rows["a"]["same_arguments"]) == ("b", True)


def test_should_report_the_forwarder_and_target_location(session, tmp_path):
    rows = listed(session, tmp_path, FORWARD)
    assert (rows["a"]["file"], rows["a"]["line"], rows["a"]["target_file"]) == ("m.py", 1, "m.py")


def test_should_flag_a_call_with_other_arguments(session, tmp_path):
    rows = listed(session, tmp_path, "def a(x):\n    b(x, 1)\n\ndef b(x, y):\n    return x\n")
    assert rows["a"]["same_arguments"] is False


def test_should_flag_arguments_in_another_order(session, tmp_path):
    rows = listed(session, tmp_path, "def a(x, y):\n    return b(y, x)\n\ndef b(x, y):\n    return x\n")
    assert rows["a"]["same_arguments"] is False


def test_should_ignore_a_leading_docstring(session, tmp_path):
    rows = listed(session, tmp_path, 'def a():\n    """Doc."""\n    return b()\n\ndef b():\n    return 1\n')
    assert "a" in rows


def test_should_not_list_a_function_with_two_statements(session, tmp_path):
    rows = listed(session, tmp_path, "def a():\n    x = 1\n    return b()\n\ndef b():\n    return 1\n")
    assert "a" not in rows


def test_should_not_list_a_function_returning_something_besides_a_call(session, tmp_path):
    rows = listed(session, tmp_path, "def a(x):\n    return b(x) + 1\n\ndef b(x):\n    return x\n")
    assert "a" not in rows


def test_should_not_list_a_forwarder_to_an_unresolved_name(session, tmp_path):
    rows = listed(session, tmp_path, "def a(x):\n    return missing(x)\n")
    assert "a" not in rows


def test_should_not_list_a_test_function(session, tmp_path):
    rows = listed(session, tmp_path, "def test_a():\n    return b()\n\ndef b():\n    return 1\n", "tests/test_m.py")
    assert "test_a" not in rows


def test_should_list_a_decorated_forwarder(session, tmp_path):
    rows = listed(session, tmp_path, "@deco\n" + FORWARD)
    assert "a" in rows


def test_should_list_an_async_forwarder(session, tmp_path):
    rows = listed(session, tmp_path, "async def a(x):\n    return await b(x)\n\nasync def b(x):\n    return x\n")
    assert "a" in rows


def test_should_list_a_method_forwarder_ignoring_self(session, tmp_path):
    source = "class C:\n    def a(self, x):\n        return self.b(x)\n\n    def b(self, x):\n        return x\n"
    rows = listed(session, tmp_path, source)
    assert (rows["C.a"]["target"], rows["C.a"]["same_arguments"]) == ("C.b", True)


def test_should_count_callers_and_order_rows_by_them(session, tmp_path):
    source = (
        "def few(x):\n    return t(x)\n\ndef many(x):\n    return t(x)\n\ndef t(x):\n    return x\n\n"
        "def c1():\n    x = 0\n    many(1)\n\ndef c2():\n    x = 0\n    many(2)\n\ndef c3():\n    x = 0\n    few(3)\n"
    )
    listed(session, tmp_path, source)
    rows = pass_through_functions()
    assert [(r["name"], r["callers"]) for r in rows] == [("many", 2), ("few", 1)]


def test_should_count_module_level_code_as_a_caller(session, tmp_path):
    rows = listed(session, tmp_path, FORWARD + "\na(1)\n")
    assert rows["a"]["callers"] == 1


def test_should_register_the_tool_with_the_server():
    import codescan_mcp_server  # noqa: F401  (importing registers every tool)
    from codescan_lib.mcp_tools.base import mcp

    assert "pass_through_functions" in {tool.name for tool in asyncio.run(mcp.list_tools())}
