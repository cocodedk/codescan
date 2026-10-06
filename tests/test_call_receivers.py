"""A call on a receiver resolves only when the receiver is certainly a project class or module."""
import pytest
from call_helpers import RUNNER, resolved_calls, rows, scan, unresolved_calls


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
