"""The scan stores complexity and max_nesting per function; most_complex_functions ranks them."""
import asyncio

import pytest
from neo4j import GraphDatabase

from codescan_lib.analysis import analyze_file, finalize_graph
from codescan_lib.constants import NEO4J_PASSWORD, NEO4J_URI, NEO4J_USER
from codescan_lib.db_operations import clear_database
from codescan_lib.mcp_tools.flow_tools import most_complex_functions
from codescan_lib.stats_collector import StatsCollector

MANY = 1000


@pytest.fixture
def session():
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    with driver.session() as s:
        yield s
    driver.close()


def scan(session, tmp_path, source, name="m.py"):
    """Scan one file into a clean graph."""
    clear_database(session, quiet=True)
    path = tmp_path / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source)
    analyze_file(str(path), session, str(tmp_path), StatsCollector(), defer_relationships=True)
    finalize_graph(session)


def rows_by_name(field):
    return {r["name"]: r[field] for r in most_complex_functions(MANY)}


def measured(session, tmp_path, body):
    """(complexity, max_nesting) of `def f(a, b, c, xs)` with the given body."""
    source = "def f(a, b, c, xs):\n" + "".join(f"    {line}\n" for line in body.splitlines())
    scan(session, tmp_path, source)
    row = {r["name"]: r for r in most_complex_functions(MANY)}["f"]
    return row["complexity"], row["max_nesting"]


def test_should_give_a_branchless_function_complexity_1_and_nesting_0(session, tmp_path):
    assert measured(session, tmp_path, "return a") == (1, 0)


def test_should_add_one_for_if_and_one_for_elif_but_none_for_else(session, tmp_path):
    body = "if a:\n    return 1\nelif b:\n    return 2\nelse:\n    return 3"
    assert measured(session, tmp_path, body)[0] == 3


def test_should_not_nest_an_elif_deeper_than_its_if(session, tmp_path):
    assert measured(session, tmp_path, "if a:\n    pass\nelif b:\n    pass\nelse:\n    pass")[1] == 1


def test_should_nest_an_if_written_inside_else(session, tmp_path):
    assert measured(session, tmp_path, "if a:\n    pass\nelse:\n    if b:\n        pass")[1] == 2


def test_should_give_a_for_with_an_if_inside_complexity_3_and_nesting_2(session, tmp_path):
    assert measured(session, tmp_path, "for x in xs:\n    if x:\n        return x") == (3, 2)


def test_should_count_a_while_loop(session, tmp_path):
    assert measured(session, tmp_path, "while a:\n    a -= 1") == (2, 1)


def test_should_count_an_async_for_loop(session, tmp_path):
    scan(session, tmp_path, "async def f(xs):\n    async for x in xs:\n        pass\n")
    assert rows_by_name("complexity")["f"] == 2


def test_should_add_one_per_extra_operand_of_and_or_or(session, tmp_path):
    assert measured(session, tmp_path, "return a and b and c")[0] == 3


def test_should_count_each_boolean_operator_of_a_mixed_expression(session, tmp_path):
    assert measured(session, tmp_path, "return a or (b and c)")[0] == 3


def test_should_add_one_for_a_conditional_expression(session, tmp_path):
    assert measured(session, tmp_path, "return a if b else c")[0] == 2


def test_should_add_one_for_an_if_inside_a_comprehension(session, tmp_path):
    assert measured(session, tmp_path, "return [v for v in xs if v]")[0] == 2


def test_should_add_one_per_if_inside_a_comprehension(session, tmp_path):
    assert measured(session, tmp_path, "return [v for v in xs if v if a]")[0] == 3


def test_should_add_one_for_each_except_handler(session, tmp_path):
    body = "try:\n    pass\nexcept KeyError:\n    pass\nexcept ValueError:\n    pass"
    assert measured(session, tmp_path, body)[0] == 3


def test_should_add_one_for_each_case_of_a_match(session, tmp_path):
    body = "match a:\n    case 1:\n        pass\n    case 2:\n        pass\n    case _:\n        pass"
    assert measured(session, tmp_path, body) == (4, 1)


def test_should_nest_with_and_try_blocks(session, tmp_path):
    body = "with a:\n    try:\n        pass\n    finally:\n        pass"
    assert measured(session, tmp_path, body) == (1, 2)


def test_should_take_the_deepest_block_as_max_nesting(session, tmp_path):
    body = "if a:\n    pass\nfor x in xs:\n    while b:\n        if c:\n            pass"
    assert measured(session, tmp_path, body)[1] == 3


def test_should_leave_a_nested_functions_branches_out_of_its_parent(session, tmp_path):
    scan(session, tmp_path, "def outer(a):\n    def inner(b):\n        if b:\n            return 1\n        return 2\n    return inner\n")
    complexity, nesting = rows_by_name("complexity"), rows_by_name("max_nesting")
    assert [(complexity[n], nesting[n]) for n in ("outer", "inner")] == [(1, 0), (2, 1)]


def test_should_leave_a_nested_classs_methods_out_of_their_parent(session, tmp_path):
    scan(session, tmp_path, "def outer(a):\n    class K:\n        def m(self, b):\n            if b:\n                pass\n    return K\n")
    complexity = rows_by_name("complexity")
    assert (complexity["outer"], complexity["K.m"]) == (1, 2)


def test_should_count_a_default_value_branch_toward_the_enclosing_function(session, tmp_path):
    scan(session, tmp_path, "def outer(a):\n    def inner(b=1 if a else 2):\n        pass\n    return inner\n")
    complexity = rows_by_name("complexity")
    assert (complexity["outer"], complexity["inner"]) == (2, 1)


def test_should_order_by_complexity_then_nesting_highest_first(session, tmp_path):
    scan(session, tmp_path, (
        "def flat(a, b):\n    return a and b\n"  # 2, 0
        "def deep(a):\n    if a:\n        pass\n"  # 2, 1
        "def big(a, b, c):\n    return a and b and c\n"  # 3, 0
        "def plain():\n    return 1\n"  # 1, 0
    ))
    assert [r["name"] for r in most_complex_functions(MANY)] == ["big", "deep", "flat", "plain"]


def test_should_report_name_file_line_length_complexity_and_nesting(session, tmp_path):
    scan(session, tmp_path, "x = 1\ndef f(a):\n    if a:\n        return 1\n    return 2\n", "pkg/m.py")
    assert most_complex_functions(MANY) == [
        {"name": "f", "file": "pkg/m.py", "line": 2, "length": 4, "complexity": 2, "max_nesting": 1}
    ]


def test_should_respect_the_limit(session, tmp_path):
    scan(session, tmp_path, "def a(x):\n    if x:\n        pass\ndef b():\n    pass\ndef c():\n    pass\n")
    assert [r["name"] for r in most_complex_functions(2)] == ["a", "b"]


def test_should_default_to_twenty_rows(session, tmp_path):
    scan(session, tmp_path, "".join(f"def f{i}():\n    pass\n" for i in range(25)))
    assert len(most_complex_functions()) == 20


def test_should_leave_out_test_functions(session, tmp_path):
    scan(session, tmp_path, "def test_a(x):\n    if x:\n        pass\n", "tests/test_m.py")
    assert most_complex_functions(MANY) == []


def test_should_leave_out_placeholders(session, tmp_path):
    scan(session, tmp_path, "def f():\n    return missing()\n")
    placeholders = session.run("MATCH (p:ReferenceFunction) RETURN count(p) AS n").single()["n"]
    assert (placeholders, [r["name"] for r in most_complex_functions(MANY)]) == (1, ["f"])


def test_should_register_the_tool_with_the_server():
    import codescan_mcp_server  # noqa: F401  (importing registers every tool)
    from codescan_lib.mcp_tools.base import mcp

    assert "most_complex_functions" in {tool.name for tool in asyncio.run(mcp.list_tools())}
