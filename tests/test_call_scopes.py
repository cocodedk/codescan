"""A call resolves only to what its scope and module bind the name to."""
import pytest
from call_helpers import R_RUN, RUNNER, resolved_calls, rows, scan, unresolved_calls


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
