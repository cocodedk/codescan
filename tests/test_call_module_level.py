"""Calls made outside every function have the file as caller."""
import pytest
from call_helpers import FOO, instantiated, module_calls, resolved_calls, rows, scan

from codescan_lib.mcp_tools.call_graph import callers, uncalled_functions


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


def test_should_not_link_a_constructor_call_on_a_name_the_function_binds(session, tmp_path):
    scan(session, tmp_path, {"m.py": FOO + "def f(Foo): Foo()\nf(lambda: None)\n"})
    assert instantiated(session) == set()


@pytest.mark.parametrize("source", [
    "def helper(): pass\nhelper = lambda: None\nhelper()\n",
    "def helper(): pass\ntry:\n    from lib import helper\nexcept ImportError:\n    pass\nhelper()\n",
])
def test_should_not_resolve_a_module_level_call_to_a_name_the_module_rebinds(session, tmp_path, source):
    scan(session, tmp_path, {"m.py": source})
    assert module_calls(session) == set()


def test_should_not_resolve_a_function_call_to_a_name_the_module_rebinds(session, tmp_path):
    scan(session, tmp_path, {"m.py": "def helper(): pass\nhelper = lambda: None\ndef f():\n    helper()\n"})
    assert ("f", "helper") not in resolved_calls(session)


def test_should_not_link_a_constructor_call_to_a_name_the_module_rebinds(session, tmp_path):
    scan(session, tmp_path, {"a.py": FOO, "m.py": "Foo = lambda: None\nFoo()\n"})
    assert instantiated(session) == set()


def test_should_not_trust_a_module_name_bound_by_assignment_as_a_receiver(session, tmp_path):
    files = {"a.py": "class A:\n    def run(): pass\n",
             "m.py": "class Other:\n    def run(): pass\nA = Other\nA.run()\n"}
    scan(session, tmp_path, files)
    assert ("m.py", "A.run") not in module_calls(session)


@pytest.mark.parametrize("source", [
    "def helper(): pass\nunused = lambda: helper()\n",
    "from __future__ import annotations\ndef helper(): pass\ndef f(x: helper()): pass\n",
    "def helper(): pass\ndef f() -> helper(): pass\n",
    "def helper(): pass\nx: helper() = 1\n",
])
def test_should_not_record_deferred_code_as_a_module_level_call(session, tmp_path, source):
    scan(session, tmp_path, {"m.py": source})
    assert module_calls(session) == set()


def test_should_record_a_lambda_default_as_a_module_level_call(session, tmp_path):
    scan(session, tmp_path, {"m.py": "def helper(): pass\nunused = lambda x=helper(): x\n"})
    assert module_calls(session) == {("m.py", "helper")}
