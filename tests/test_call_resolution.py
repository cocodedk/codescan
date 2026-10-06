"""Call and test-relationship results must not depend on file order or call shape."""
import pytest
from neo4j import GraphDatabase

from codescan_lib.analysis import analyze_directory, analyze_file, finalize_graph
from codescan_lib.constants import NEO4J_PASSWORD, NEO4J_URI, NEO4J_USER
from codescan_lib.db_operations import clear_database
from codescan_lib.stats_collector import StatsCollector


@pytest.fixture
def session():
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    with driver.session() as s:
        yield s
    driver.close()


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


def test_should_record_calls_nested_in_builtin_arguments(session, tmp_path):
    scan(session, tmp_path, {"m.py": "def helper(): pass\ndef f():\n    print(helper())\n"})
    assert ("f", "helper") in resolved_calls(session)


def test_should_record_calls_made_by_async_functions(session, tmp_path):
    scan(session, tmp_path, {"m.py": "def helper(): pass\nasync def f():\n    helper()\n"})
    assert ("f", "helper") in resolved_calls(session)


def test_should_attribute_calls_after_a_nested_function_to_the_outer_one(session, tmp_path):
    source = "def helper(): pass\ndef outer():\n    def inner(): pass\n    helper()\n"
    scan(session, tmp_path, {"m.py": source})
    assert ("outer", "helper") in resolved_calls(session)


@pytest.mark.parametrize("order", [["caller.py", "lib.py"], ["lib.py", "caller.py"]])
def test_should_resolve_method_calls_in_any_file_order(session, tmp_path, order):
    files = {
        "caller.py": "def use(g):\n    g.hello()\n",
        "lib.py": "class Greeter:\n    def hello(self): pass\n",
    }
    scan(session, tmp_path, files, order)
    assert ("use", "Greeter.hello") in resolved_calls(session)


def test_should_prefer_the_method_of_the_calling_class(session, tmp_path):
    source = (
        "class A:\n    def go(self):\n        self.run()\n    def run(self): pass\n"
        "class B:\n    def run(self): pass\n"
    )
    scan(session, tmp_path, {"m.py": source})
    assert ("A.go", "B.run") not in resolved_calls(session)


def test_should_resolve_the_method_of_the_calling_class(session, tmp_path):
    source = (
        "class A:\n    def go(self):\n        self.run()\n    def run(self): pass\n"
        "class B:\n    def run(self): pass\n"
    )
    scan(session, tmp_path, {"m.py": source})
    assert ("A.go", "A.run") in resolved_calls(session)


def test_should_leave_ambiguous_calls_unresolved(session, tmp_path):
    files = {"m.py": "def go():\n    thing()\n", "a.py": "def thing(): pass\n", "b.py": "def thing(): pass\n"}
    scan(session, tmp_path, files)
    assert ("go", "thing") in unresolved_calls(session)


def test_should_resolve_builtin_named_methods(session, tmp_path):
    source = "class P:\n    def go(self):\n        self.open()\n    def open(self): pass\n"
    scan(session, tmp_path, {"m.py": source})
    assert ("P.go", "P.open") in resolved_calls(session)


def test_should_ignore_calls_rooted_in_the_standard_library(session, tmp_path):
    scan(session, tmp_path, {"m.py": "import os\ndef f():\n    return os.path.join('a')\n"})
    assert unresolved_calls(session) == set()


def test_should_link_tests_to_code_analyzed_after_the_test_file(session, tmp_path):
    files = {"tests/test_m.py": "def test_helper(): pass\n", "m.py": "def helper(): pass\n"}
    scan(session, tmp_path, files, ["tests/test_m.py", "m.py"])
    tests = rows(session, "MATCH (t:TestFunction)-[:TESTS]->(p:Function) RETURN t.name, p.name")
    assert ("test_helper", "helper") in tests


def test_should_link_tests_to_methods_by_simple_name(session, tmp_path):
    files = {"tests/test_m.py": "def test_hello(): pass\n", "m.py": "class G:\n    def hello(self): pass\n"}
    scan(session, tmp_path, files)
    tests = rows(session, "MATCH (t:TestFunction)-[:TESTS]->(p:Function) RETURN t.name, p.name")
    assert ("test_hello", "G.hello") in tests


def test_should_not_count_skipped_dunder_methods_as_skipped_files(session, tmp_path):
    stats = scan(session, tmp_path, {"m.py": "class A:\n    def __init__(self): pass\n"})
    assert stats.files_skipped == 0


def test_should_record_annotated_constants(session, tmp_path):
    scan(session, tmp_path, {"m.py": "A_B: int = 3\n"})
    assert rows(session, "MATCH (c:Constant) RETURN c.name, c.value") == {("A_B", "3")}


def test_should_keep_constant_expressions_readable(session, tmp_path):
    scan(session, tmp_path, {"m.py": "A_B = 3\nMAX_X = A_B * 2\n"})
    values = rows(session, "MATCH (c:Constant {name: 'MAX_X'}) RETURN c.value, c.type")
    assert values == {("A_B * 2", "expression")}


def test_should_not_link_tests_to_unresolved_placeholders(session, tmp_path):
    scan(session, tmp_path, {"tests/test_m.py": "def test_x():\n    assertEqual(1, 1)\n"})
    tests = rows(session, "MATCH (:TestFunction)-[:TESTS]->(p:Function) RETURN p.name")
    assert tests == set()


def test_should_scan_test_files_with_relative_imports(session, tmp_path):
    stats = scan(session, tmp_path, {"tests/test_m.py": "from . import helpers\ndef test_x(): pass\n"})
    assert stats.files_error == 0


def test_should_not_treat_placeholders_as_file_contents(session, tmp_path):
    scan(session, tmp_path, {"m.py": "def f():\n    undefined()\n"})
    contained = rows(session, "MATCH (:File)-[:CONTAINS]->(fn:Function) RETURN fn.name")
    assert contained == {("f",)}


def test_should_resolve_calls_to_overloaded_definitions(session, tmp_path):
    source = "def f(a): pass\ndef f(a, b=1): pass\ndef g():\n    f(1)\n"
    scan(session, tmp_path, {"m.py": source})
    assert ("g", "f") in resolved_calls(session)


def test_should_not_let_placeholders_act_as_callers(session, tmp_path):
    files = {
        "a.py": "def main():\n    run()\ndef run():\n    work()\n",
        "b.py": "def go(x):\n    x.run()\n",
        "c.py": "def run(): pass\n",
    }
    scan(session, tmp_path, files)
    assert rows(session, "MATCH (:ReferenceFunction)-[r:CALLS]->() RETURN count(r)") == {(0,)}


def test_should_not_resolve_attribute_calls_to_the_calling_method(session, tmp_path):
    source = "class Wrapper:\n    def close(self):\n        self.r.close()\n"
    scan(session, tmp_path, {"m.py": source})
    assert ("Wrapper.close", "Wrapper.close") not in resolved_calls(session)


def test_should_not_resolve_attribute_calls_to_a_same_named_function(session, tmp_path):
    scan(session, tmp_path, {"m.py": "def connect():\n    return db.connect()\n"})
    assert ("connect", "connect") not in resolved_calls(session)


def test_should_tell_same_named_functions_apart_as_callers(session, tmp_path):
    source = "def helper(): pass\ndef log(): pass\ndef outer():\n    def helper():\n        log()\n    helper()\n"
    scan(session, tmp_path, {"m.py": source})
    callers = rows(session, "MATCH (h:Function {name: 'helper'})-[:CALLS]->(:Function {name: 'log'}) RETURN h.line")
    assert callers == {(4,)}


def test_should_keep_each_call_on_a_line_that_resolves_differently(session, tmp_path):
    files = {
        "m.py": "class M:\n    def foo(self, a): pass\ndef go(x):\n    return foo(1) + x.foo(2)\n",
        "a.py": "def foo(a): pass\n",
        "b.py": "def foo(a): pass\n",
    }
    scan(session, tmp_path, files)
    assert ("go", "foo") in unresolved_calls(session)


def test_should_count_only_unresolved_calls_as_reference_functions(session, tmp_path):
    (tmp_path / "m.py").write_text("def helper(): pass\ndef f():\n    helper()\n    helper()\n")
    clear_database(session, quiet=True)
    stats = analyze_directory(str(tmp_path), session)
    assert (stats.elements["functions"], stats.elements["reference_functions"]) == (2, 0)

