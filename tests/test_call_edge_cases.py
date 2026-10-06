"""Decorated classes, same-file preference and scope bindings in call resolution."""
import pytest
from call_helpers import FOO, instantiated, module_calls, resolved_calls, scan

from codescan_lib.mcp_tools.call_graph import most_called_functions


def test_should_not_link_a_constructor_call_to_a_class_replaced_by_its_decorator(session, tmp_path):
    source = "def decorate(cls): return lambda: 42\n@decorate\nclass Foo: pass\nFoo()\n"
    scan(session, tmp_path, {"m.py": source})
    assert instantiated(session) == set()


@pytest.mark.parametrize("decorator", [
    "@dataclass", "@dataclass(frozen=True)", "@dataclasses.dataclass", "@dataclasses.dataclass(frozen=True)",
    "@functools.total_ordering", "@typing.final",
])
def test_should_link_a_constructor_call_to_a_class_with_a_known_decorator(session, tmp_path, decorator):
    source = f"import dataclasses, functools, typing\nfrom dataclasses import dataclass\n{decorator}\nclass Foo: pass\nFoo()\n"
    scan(session, tmp_path, {"m.py": source})
    assert instantiated(session) == {("m.py", "Foo", "m.py")}


def test_should_not_trust_a_decorator_named_like_a_known_one_when_it_is_defined_here(session, tmp_path):
    source = "def dataclass(cls): return lambda: 42\n@dataclass\nclass Foo: pass\nFoo()\n"
    scan(session, tmp_path, {"m.py": source})
    assert instantiated(session) == set()


def test_should_prefer_a_same_file_function_over_a_class_in_another_file(session, tmp_path):
    files = {"m.py": "def helper(): pass\ndef f():\n    helper()\n", "other.py": "class helper: pass\n"}
    scan(session, tmp_path, files)
    assert (("f", "helper") in resolved_calls(session), instantiated(session)) == (True, set())


def test_should_prefer_a_same_file_class_over_a_function_in_another_file(session, tmp_path):
    scan(session, tmp_path, {"m.py": FOO + "def f():\n    Foo()\n", "other.py": "def Foo(): pass\n"})
    assert (("f", "Foo") in resolved_calls(session), instantiated(session)) == (False, {("f", "Foo", "m.py")})


def test_should_resolve_a_call_on_a_module_imported_in_a_class_body(session, tmp_path):
    source = "def f():\n    class C:\n        import lib\n        lib.helper()\n"
    scan(session, tmp_path, {"lib.py": "def helper(): pass\n", "m.py": source})
    assert ("f", "helper") in resolved_calls(session)


def test_should_count_a_file_caller_in_most_called_functions(session, tmp_path):
    scan(session, tmp_path, {"m.py": "def main(): pass\nmain()\n"})
    assert {r["name"]: r["num_callers"] for r in most_called_functions(limit=100)} == {"main": 1}


@pytest.mark.parametrize("body", [
    "def f(helper):\n    helper()\n",
    "def f(x):\n    helper = x\n    helper()\n",
    "def f(x):\n    for helper in x:\n        helper()\n",
    "def outer(helper):\n    def inner():\n        helper()\n",
    "def f():\n    class helper: pass\n    helper()\n",
])
def test_should_not_resolve_a_bare_call_to_a_function_when_the_calling_scope_binds_the_name(session, tmp_path, body):
    scan(session, tmp_path, {"m.py": "def helper(): pass\n" + body})
    assert not {c for c, t in resolved_calls(session) if t == "helper"}


def test_should_resolve_a_bare_call_to_the_nearest_scopes_nested_def(session, tmp_path):
    source = "def outer(helper):\n    def inner():\n        def helper(): pass\n        helper()\n"
    scan(session, tmp_path, {"m.py": source})
    assert ("inner", "helper") in resolved_calls(session)


@pytest.mark.parametrize("header", [
    "from unittest.mock import Mock as dataclass", "from mylib import dataclass", "import mylib as dataclasses",
])
def test_should_not_trust_a_known_decorator_name_that_was_imported_from_elsewhere(session, tmp_path, header):
    decorator = "@dataclasses.dataclass" if "dataclasses" in header else "@dataclass"
    scan(session, tmp_path, {"m.py": f"{header}\n{decorator}\nclass Foo: pass\nFoo()\n"})
    assert instantiated(session) == set()


def test_should_trust_a_known_decorator_imported_under_another_name(session, tmp_path):
    source = "from dataclasses import dataclass as dc\n@dc\nclass Foo: pass\nFoo()\n"
    scan(session, tmp_path, {"m.py": source})
    assert instantiated(session) == {("m.py", "Foo", "m.py")}


@pytest.mark.parametrize("source", [
    "def helper(): return int\npending = (helper() for _ in [1])\n",
    "def helper(): return int\ntype Alias = helper()\n",
])
def test_should_not_record_lazy_code_as_a_module_level_call(session, tmp_path, source):
    scan(session, tmp_path, {"m.py": source})
    assert module_calls(session) == set()


@pytest.mark.parametrize("source", [
    "def helper(): return [1]\nitems = [x for x in helper()]\n",
    "def helper(): return [1]\nitems = [x for x in [1] if helper()]\n",
    "def helper(): return [1]\nitems = (x for x in helper())\n",
])
def test_should_record_eager_module_level_calls_in_comprehensions(session, tmp_path, source):
    scan(session, tmp_path, {"m.py": source})
    assert module_calls(session) == {("m.py", "helper")}


def test_should_not_resolve_a_call_to_another_files_function_when_the_module_assigns_the_name(session, tmp_path):
    scan(session, tmp_path, {"a.py": "def helper(): return 1\n", "m.py": "helper = lambda: 2\nhelper()\n"})
    assert module_calls(session) == set()
