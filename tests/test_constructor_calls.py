"""A call that builds a project class links to the class."""
from call_helpers import FOO, instantiated, module_calls, rows, scan, unresolved_calls


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
