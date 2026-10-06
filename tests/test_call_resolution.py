"""Call and test-relationship results must not depend on file order or call shape."""
import pytest
from neo4j import GraphDatabase

from codescan_lib.analysis import analyze_directory, analyze_file, finalize_graph
from codescan_lib.constants import NEO4J_PASSWORD, NEO4J_URI, NEO4J_USER
from codescan_lib.db_operations import clear_database
from codescan_lib.mcp_tools.call_graph import callers, uncalled_functions
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
        "caller.py": "def use():\n    g = Greeter()\n    g.hello()\n",
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



def test_should_index_the_lookups_a_scan_makes(session, tmp_path):
    (tmp_path / "m.py").write_text("def f(): pass\n")
    analyze_directory(str(tmp_path), session)
    indexed = {
        (tuple(r["labelsOrTypes"]), tuple(r["properties"]))
        for r in session.run("SHOW INDEXES YIELD labelsOrTypes, properties WHERE labelsOrTypes IS NOT NULL "
                             "RETURN labelsOrTypes, properties")
    }
    assert {(("Function",), ("name", "file")), (("Class",), ("name", "file")), (("Constant",), ("name", "file")),
            (("File",), ("path",)), (("ReferenceFunction",), ("name",))} <= indexed


RUNNER = "class Runner:\n    def run(self): pass\n"


def test_should_leave_calls_on_a_parameter_unresolved(session, tmp_path):
    scan(session, tmp_path, {"m.py": RUNNER + 'def fetch(session):\n    session.run("x")\n'})
    assert ("fetch", "run") in unresolved_calls(session)


def test_should_not_resolve_calls_on_a_parameter_to_a_method(session, tmp_path):
    scan(session, tmp_path, {"m.py": RUNNER + 'def fetch(session):\n    session.run("x")\n'})
    assert ("fetch", "Runner.run") not in resolved_calls(session)


@pytest.mark.parametrize("source", [
    "import requests\ndef f(u):\n    return requests.get(u)\n",
    "from neo4j import GraphDatabase\ndef f(u):\n    return GraphDatabase.driver(u)\n",
    "import requests as rq\ndef f(u):\n    return rq.adapters.HTTPAdapter(u)\n",
])
def test_should_record_no_call_for_third_party_receivers(session, tmp_path, source):
    scan(session, tmp_path, {"m.py": source})
    assert (resolved_calls(session), unresolved_calls(session)) == (set(), set())


def test_should_keep_calls_on_project_imports(session, tmp_path):
    files = {"pkg/__init__.py": "", "pkg/lib.py": "def go(): pass\n", "m.py": "from pkg import lib\ndef f():\n    lib.go()\n"}
    scan(session, tmp_path, files)
    assert ("f", "go") in resolved_calls(session)


def test_should_resolve_calls_on_a_local_instance(session, tmp_path):
    scan(session, tmp_path, {"m.py": RUNNER + "def f():\n    x = Runner()\n    x.run()\n"})
    assert ("f", "Runner.run") in resolved_calls(session)


def test_should_resolve_calls_on_a_class(session, tmp_path):
    scan(session, tmp_path, {"m.py": RUNNER + "def f():\n    Runner.run()\n"})
    assert ("f", "Runner.run") in resolved_calls(session)


def test_should_not_resolve_calls_on_an_instance_bound_in_another_function(session, tmp_path):
    source = RUNNER + "def a():\n    x = Runner()\ndef b(x):\n    x.run()\n"
    scan(session, tmp_path, {"m.py": source})
    assert ("b", "run") in unresolved_calls(session)


@pytest.mark.parametrize("imports", ["import pkg.utils as utils", "from pkg import utils"])
def test_should_resolve_calls_on_a_project_module_alias(session, tmp_path, imports):
    files = {"pkg/__init__.py": "", "pkg/utils.py": "def helper(): pass\n", "m.py": imports + "\ndef f():\n    utils.helper()\n"}
    scan(session, tmp_path, files)
    assert ("f", "helper") in resolved_calls(session)


def test_should_resolve_calls_on_a_dotted_project_module(session, tmp_path):
    files = {"pkg/__init__.py": "", "pkg/utils.py": "def helper(): pass\n", "m.py": "import pkg.utils\ndef f():\n    pkg.utils.helper()\n"}
    scan(session, tmp_path, files)
    assert ("f", "helper") in resolved_calls(session)


def test_should_not_resolve_module_calls_to_another_modules_function(session, tmp_path):
    files = {"pkg/__init__.py": "", "pkg/utils.py": "def other(): pass\n", "pkg/more.py": "def helper(): pass\n",
             "m.py": "from pkg import utils\ndef f():\n    utils.helper()\n"}
    scan(session, tmp_path, files)
    assert ("f", "helper") in unresolved_calls(session)


def test_should_link_each_nested_helper_call_to_its_own_parents_helper(session, tmp_path):
    source = (
        "def outer1():\n    def helper(): pass\n    helper()\n"
        "def outer2():\n    def helper(): pass\n    helper()\n"
    )
    scan(session, tmp_path, {"m.py": source})
    edges = rows(session, """
        MATCH (a:Function)-[:CALLS]->(b:Function {name: 'helper'}) RETURN a.name, b.line""")
    assert edges == {("outer1", 2), ("outer2", 5)}


def test_should_resolve_a_nested_call_from_a_sibling_to_the_enclosing_functions_helper(session, tmp_path):
    source = "def outer():\n    def helper(): pass\n    def inner():\n        helper()\n"
    scan(session, tmp_path, {"m.py": source})
    assert ("inner", "helper") in resolved_calls(session)


def test_should_prefer_the_module_level_function_over_a_nested_one_for_outside_calls(session, tmp_path):
    source = "def helper(): pass\ndef outer():\n    def helper(): pass\ndef third():\n    helper()\n"
    scan(session, tmp_path, {"m.py": source})
    edges = rows(session, "MATCH (:Function {name: 'third'})-[:CALLS]->(b:Function) RETURN b.line")
    assert edges == {(1,)}


def test_should_not_link_outside_calls_to_a_function_nested_elsewhere(session, tmp_path):
    scan(session, tmp_path, {"m.py": "def outer():\n    def helper(): pass\ndef third():\n    helper()\n"})
    assert ("third", "helper") in unresolved_calls(session)


def test_should_keep_every_module_level_definition_as_a_target(session, tmp_path):
    scan(session, tmp_path, {"m.py": "def f(a): pass\ndef f(a, b=1): pass\ndef g():\n    f(1)\n"})
    edges = rows(session, "MATCH (:Function {name: 'g'})-[:CALLS]->(b:Function) RETURN b.line")
    assert edges == {(1,), (2,)}


@pytest.mark.parametrize(("source", "kind"), [
    ("def helper(): pass\ndef f():\n    helper()\n", "bare"),
    ("class A:\n    def go(self):\n        self.run()\n    def run(self): pass\n", "self"),
    (RUNNER + "def f():\n    x = Runner()\n    x.run()\n", "attr"),
])
def test_should_keep_the_call_kind_on_resolved_edges(session, tmp_path, source, kind):
    scan(session, tmp_path, {"m.py": source})
    assert rows(session, "MATCH (:Function)-[r:CALLS]->(b:Function) WHERE b.is_reference = false "
                         "RETURN r.kind") == {(kind,)}


def test_should_resolve_calls_on_a_relatively_imported_module(session, tmp_path):
    files = {"pkg/__init__.py": "", "pkg/utils.py": "def helper(): pass\n",
             "pkg/m.py": "from . import utils\ndef f():\n    utils.helper()\n"}
    scan(session, tmp_path, files)
    assert ("f", "helper") in resolved_calls(session)


def test_should_keep_an_unresolved_call_on_the_same_line_as_a_resolved_one(session, tmp_path):
    scan(session, tmp_path, {"m.py": RUNNER + "def f(session):\n    Runner.run(); session.run()\n"})
    assert (("f", "Runner.run") in resolved_calls(session), ("f", "run") in unresolved_calls(session)) == (True, True)


def test_should_not_resolve_calls_on_a_parameter_named_like_a_module(session, tmp_path):
    scan(session, tmp_path, {"utils.py": "def helper(): pass\n", "m.py": "def f(utils):\n    utils.helper()\n"})
    assert ("f", "helper") in unresolved_calls(session)


def test_should_resolve_a_class_call_only_in_the_imported_module(session, tmp_path):
    files = {"b.py": "class Runner: pass\n", "a.py": RUNNER, "m.py": "from b import Runner\ndef f():\n    Runner.run()\n"}
    scan(session, tmp_path, files)
    assert ("f", "run") in unresolved_calls(session)


def test_should_keep_a_function_local_import_inside_that_function(session, tmp_path):
    source = "def first():\n    import requests as service\ndef second(service):\n    service.get()\n"
    scan(session, tmp_path, {"m.py": source})
    assert ("second", "get") in unresolved_calls(session)


def test_should_resolve_an_instance_built_by_a_qualified_class(session, tmp_path):
    files = {"models.py": RUNNER, "m.py": RUNNER + "import models\ndef f():\n    x = models.Runner()\n    x.run()\n"}
    scan(session, tmp_path, files)
    assert rows(session, "MATCH (:Function {name: 'f'})-[:CALLS]->(b:Function {is_reference: false}) RETURN b.file") == {("models.py",)}


def test_should_resolve_an_instance_built_by_an_aliased_import(session, tmp_path):
    files = {"models.py": RUNNER, "m.py": "from models import Runner as R\ndef f():\n    x = R()\n    x.run()\n"}
    scan(session, tmp_path, files)
    assert ("f", "Runner.run") in resolved_calls(session)


@pytest.mark.parametrize("rebinding", [
    "x, = other", "x += other", "for x in other: pass", "with other as x: pass", "(x := other)", "del x",
])
def test_should_forget_an_instance_when_its_name_is_rebound(session, tmp_path, rebinding):
    source = RUNNER + f"def f(other):\n    x = Runner()\n    {rebinding}\n    x.run()\n"
    scan(session, tmp_path, {"m.py": source})
    assert ("f", "Runner.run") not in resolved_calls(session)


def test_should_leave_a_call_unresolved_when_its_name_is_assigned_twice(session, tmp_path):
    source = ("class A:\n    def run(self): pass\nclass B:\n    def run(self): pass\n"
              "def f():\n    x = A()\n    x = B(x.run())\n")
    scan(session, tmp_path, {"m.py": source})
    assert {t for c, t in resolved_calls(session) if c == "f"} == set()


def test_should_not_resolve_an_imported_call_to_a_name_the_other_file_defines_twice(session, tmp_path):
    files = {"lib.py": "def f(a): pass\ndef f(a, b=1): pass\n", "m.py": "from lib import f\ndef g():\n    f(1)\n"}
    scan(session, tmp_path, files)
    assert rows(session, "MATCH (:Function {name: 'g'})-[:CALLS]->(b:Function {is_reference: false}) RETURN b.line") == set()


R_RUN = "class R:\n    def run(self): pass\n"


@pytest.mark.parametrize("source", [
    "import lib\ndef f(lib):\n    lib.run()\n",
    "import lib\ndef f(other):\n    lib = other\n    lib.run()\n",
    "import lib\ndef f(lib):\n    def inner():\n        lib.run()\n",
])
def test_should_not_resolve_a_module_call_when_the_function_rebinds_the_name(session, tmp_path, source):
    scan(session, tmp_path, {"lib.py": "def run(): pass\n", "m.py": source})
    assert not {c for c, t in resolved_calls(session) if t == "run"}


@pytest.mark.parametrize("body", [
    "def f(other):\n    x = R()\n    match other:\n        case x:\n            x.run()\n",
    "def f(x):\n    class Inner:\n        x = R()\n    x.run()\n",
    "def f():\n    x = R()\n    (x := x.run())\n",
    "def f():\n    x = R(); x.run()\n",
])
def test_should_leave_calls_unresolved_unless_the_instance_is_the_names_only_binding(session, tmp_path, body):
    scan(session, tmp_path, {"m.py": R_RUN + body})
    assert (("f", "R.run") in resolved_calls(session), ("f", "run") in unresolved_calls(session)) == (False, True)


def test_should_not_resolve_a_call_in_a_comprehension_that_rebinds_the_instance_name(session, tmp_path):
    scan(session, tmp_path, {"m.py": R_RUN + "def f(xs):\n    x = R()\n    [x.run() for x in xs]\n    x.run()\n"})
    assert ("f", "R.run") not in resolved_calls(session)


def test_should_not_count_an_annotation_without_a_value_as_a_binding(session, tmp_path):
    scan(session, tmp_path, {"m.py": R_RUN + "def f():\n    x = R()\n    x: object\n    x.run()\n"})
    assert ("f", "R.run") in resolved_calls(session)


def test_should_not_resolve_a_closures_import_receiver_rebound_later_in_the_enclosing_function(session, tmp_path):
    source = "import a as lib\ndef outer():\n    def inner():\n        lib.run()\n    import b as lib\n    inner()\n"
    scan(session, tmp_path, {"a.py": "def run(): pass\n", "b.py": "def run(): pass\n", "m.py": source})
    assert not {c for c, t in resolved_calls(session) if c == "inner"}


def test_should_resolve_a_module_alias_call_only_to_functions_of_that_modules_file(session, tmp_path):
    files = {
        "pkg/__init__.py": "class utils:\n    @staticmethod\n    def helper(): pass\n",
        "pkg/utils.py": "def helper(): pass\n",
        "other.py": "class More:\n    def helper(self): pass\n",
        "m.py": "import pkg.utils as utils\ndef f():\n    utils.helper()\n",
    }
    scan(session, tmp_path, files)
    edges = rows(session, "MATCH (:Function {name: 'f'})-[:CALLS]->(b:Function {is_reference: false}) RETURN b.name, b.file")
    assert edges == {("helper", "pkg/utils.py")}


def instantiated(session):
    return rows(session, "MATCH (a)-[:INSTANTIATES]->(c:Class) RETURN coalesce(a.name, a.path), c.name, c.file")


def module_calls(session):
    return rows(session, "MATCH (a:File)-[:CALLS]->(b:Function {is_reference: false}) RETURN a.path, b.name")


FOO = "class Foo: pass\n"


def test_should_link_a_constructor_call_to_the_class_in_another_file(session, tmp_path):
    scan(session, tmp_path, {"lib.py": FOO, "m.py": "def f():\n    Foo()\n"})
    assert instantiated(session) == {("f", "Foo", "lib.py")}


def test_should_not_leave_a_placeholder_for_a_constructor_call_that_resolved(session, tmp_path):
    scan(session, tmp_path, {"lib.py": FOO, "m.py": "def f():\n    Foo()\n"})
    assert unresolved_calls(session) == set()


def test_should_keep_a_constructor_call_unresolved_when_no_class_has_that_name(session, tmp_path):
    scan(session, tmp_path, {"m.py": "def f():\n    Foo()\n"})
    assert (("f", "Foo") in unresolved_calls(session), instantiated(session)) == (True, set())


def test_should_keep_the_line_and_arguments_on_an_instantiates_edge(session, tmp_path):
    scan(session, tmp_path, {"m.py": FOO + "def f():\n    Foo(1, 2)\n"})
    assert rows(session, "MATCH ()-[r:INSTANTIATES]->() RETURN r.line, r.args") == {(3, "1, 2")}


def test_should_prefer_the_class_in_the_same_file(session, tmp_path):
    scan(session, tmp_path, {"a.py": FOO, "m.py": FOO + "def f():\n    Foo()\n"})
    assert instantiated(session) == {("f", "Foo", "m.py")}


def test_should_leave_a_constructor_call_unresolved_when_two_files_define_the_class(session, tmp_path):
    scan(session, tmp_path, {"a.py": FOO, "b.py": FOO, "m.py": "def f():\n    Foo()\n"})
    assert instantiated(session) == set()


def test_should_not_link_a_constructor_call_to_a_class_nested_in_a_function(session, tmp_path):
    scan(session, tmp_path, {"a.py": "def g():\n    class Foo: pass\n", "m.py": "def f():\n    Foo()\n"})
    assert instantiated(session) == set()


def test_should_leave_a_name_unresolved_when_both_a_class_and_a_function_could_be_meant(session, tmp_path):
    scan(session, tmp_path, {"a.py": FOO, "b.py": "def Foo(): pass\n", "m.py": "def f():\n    Foo()\n"})
    assert (instantiated(session), module_calls(session), ("f", "Foo") in unresolved_calls(session)) == (set(), set(), True)


def test_should_link_a_constructor_call_through_a_from_import(session, tmp_path):
    scan(session, tmp_path, {"lib.py": FOO, "m.py": "from lib import Foo\ndef f():\n    Foo()\n"})
    assert instantiated(session) == {("f", "Foo", "lib.py")}


def test_should_not_link_a_constructor_call_through_an_import_of_another_module(session, tmp_path):
    files = {"a.py": FOO, "lib.py": "x = 1\n", "m.py": "from lib import Foo\ndef f():\n    Foo()\n"}
    scan(session, tmp_path, files)
    assert instantiated(session) == set()


def test_should_link_a_constructor_call_through_a_module_alias(session, tmp_path):
    scan(session, tmp_path, {"models.py": FOO, "m.py": "import models\ndef f():\n    models.Foo()\n"})
    assert instantiated(session) == {("f", "Foo", "models.py")}


def test_should_not_link_a_constructor_call_through_another_modules_class(session, tmp_path):
    files = {"a.py": FOO, "models.py": "x = 1\n", "m.py": "import models\ndef f():\n    models.Foo()\n"}
    scan(session, tmp_path, files)
    assert instantiated(session) == set()


def test_should_not_link_a_constructor_call_on_an_instance_attribute(session, tmp_path):
    scan(session, tmp_path, {"m.py": FOO + "def f(x):\n    x.Foo()\n"})
    assert instantiated(session) == set()


def test_should_record_a_module_level_call_with_the_file_as_caller(session, tmp_path):
    scan(session, tmp_path, {"m.py": 'def main(): pass\nif __name__ == "__main__":\n    main()\n'})
    assert module_calls(session) == {("m.py", "main")}


def test_should_not_list_a_function_called_only_from_module_level_as_uncalled(session, tmp_path):
    scan(session, tmp_path, {"m.py": 'def main(): pass\nif __name__ == "__main__":\n    main()\n'})
    assert "main" not in {r["name"] for r in uncalled_functions()}


def test_should_record_an_assigned_module_level_call(session, tmp_path):
    scan(session, tmp_path, {"m.py": "def helper(): pass\nx = helper()\n"})
    assert module_calls(session) == {("m.py", "helper")}


def test_should_record_a_module_level_constructor_call(session, tmp_path):
    scan(session, tmp_path, {"m.py": FOO + "x = Foo()\n"})
    assert instantiated(session) == {("m.py", "Foo", "m.py")}


def test_should_record_a_decorator_call_as_a_module_level_call(session, tmp_path):
    scan(session, tmp_path, {"m.py": "def route(p): pass\n@route('/')\ndef view(): pass\n"})
    assert module_calls(session) == {("m.py", "route")}


def test_should_record_a_class_body_call_as_a_module_level_call(session, tmp_path):
    scan(session, tmp_path, {"m.py": "def make(): pass\nclass A:\n    x = make()\n"})
    assert module_calls(session) == {("m.py", "make")}


def test_should_keep_the_call_kind_on_a_module_level_edge(session, tmp_path):
    scan(session, tmp_path, {"m.py": "def helper(): pass\nhelper()\n"})
    assert rows(session, "MATCH (:File)-[r:CALLS]->(:Function) RETURN r.kind, r.line, r.args") == {("bare", 2, "")}


def test_should_resolve_a_module_level_call_through_an_import(session, tmp_path):
    scan(session, tmp_path, {"lib.py": "def go(): pass\n", "m.py": "from lib import go\ngo()\n"})
    assert module_calls(session) == {("m.py", "go")}


def test_should_leave_an_ambiguous_module_level_call_unresolved(session, tmp_path):
    scan(session, tmp_path, {"a.py": "def go(): pass\n", "b.py": "def go(): pass\n", "m.py": "go()\n"})
    assert (module_calls(session), rows(session, "MATCH (:File)-[:CALLS]->(r:ReferenceFunction) RETURN r.name")) == (
        set(), {("go",)})


def test_should_not_resolve_a_module_level_self_call_to_a_method(session, tmp_path):
    scan(session, tmp_path, {"m.py": "class A:\n    def run(self): pass\n    x = self.run()\n"})
    assert module_calls(session) == set()


def test_should_return_a_file_caller_by_its_path(session, tmp_path):
    scan(session, tmp_path, {"m.py": "def helper(): pass\nhelper()\n"})
    assert {r["caller"] for r in callers("helper")} == {"m.py"}
