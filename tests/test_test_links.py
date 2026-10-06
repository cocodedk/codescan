"""Tests link to the code they test by name, by test class and through the names they import."""
from unittest.mock import patch

import pytest
from neo4j import GraphDatabase
from test_call_resolution import rows, scan

from codescan_lib.constants import NEO4J_PASSWORD, NEO4J_URI, NEO4J_USER

FUNCTION_LINKS = "MATCH (t:TestFunction)-[:TESTS]->(p:Function) RETURN t.name, p.name"
CLASS_LINKS = "MATCH (t:TestClass)-[:TESTS]->(c:Class) RETURN t.name, c.name"
TWO_RUNNERS = "class A:\n    def run(self): pass\nclass B:\n    def run(self): pass\n"


@pytest.fixture
def session():
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    with driver.session() as s:
        yield s
    driver.close()


def test_should_link_a_test_method_to_the_function_it_is_named_after(session, tmp_path):
    test = "import unittest\nclass TestCompute(unittest.TestCase):\n    def test_compute(self): pass\n"
    scan(session, tmp_path, {"tests/test_m.py": test, "m.py": "def compute(): pass\n"})
    assert ("TestCompute.test_compute", "compute") in rows(session, FUNCTION_LINKS)


def test_should_link_a_test_to_the_function_its_name_starts_with(session, tmp_path):
    files = {"tests/test_m.py": "def test_compute_doubles(): pass\n", "m.py": "def compute(): pass\n"}
    scan(session, tmp_path, files)
    assert rows(session, FUNCTION_LINKS) == {("test_compute_doubles", "compute")}


def test_should_link_a_test_to_the_longest_function_name_that_starts_it(session, tmp_path):
    files = {
        "tests/test_m.py": "def test_compute_all_x(): pass\n",
        "m.py": "def compute(): pass\ndef compute_all(): pass\n",
    }
    scan(session, tmp_path, files)
    assert rows(session, FUNCTION_LINKS) == {("test_compute_all_x", "compute_all")}


def test_should_not_link_a_test_to_a_function_whose_name_only_shares_letters(session, tmp_path):
    files = {"tests/test_m.py": "def test_computed(): pass\n", "m.py": "def compute(): pass\n"}
    scan(session, tmp_path, files)
    assert rows(session, FUNCTION_LINKS) == set()


def test_should_not_link_a_name_match_that_two_functions_share(session, tmp_path):
    scan(session, tmp_path, {"tests/test_m.py": "def test_run(): pass\n", "m.py": TWO_RUNNERS})
    assert rows(session, FUNCTION_LINKS) == set()


def test_should_link_a_test_class_named_with_a_prefix_to_its_class(session, tmp_path):
    scan(session, tmp_path, {"tests/test_m.py": "class TestFoo: pass\n", "m.py": "class Foo: pass\n"})
    assert rows(session, CLASS_LINKS) == {("TestFoo", "Foo")}


def test_should_link_a_test_class_named_with_a_suffix_to_its_class(session, tmp_path):
    scan(session, tmp_path, {"tests/test_m.py": "class FooTest: pass\n", "m.py": "class Foo: pass\n"})
    assert rows(session, CLASS_LINKS) == {("FooTest", "Foo")}


def test_should_not_link_a_test_class_to_a_class_name_two_files_share(session, tmp_path):
    files = {"tests/test_m.py": "class TestFoo: pass\n", "a.py": "class Foo: pass\n", "b.py": "class Foo: pass\n"}
    scan(session, tmp_path, files)
    assert rows(session, CLASS_LINKS) == set()


def test_should_resolve_a_test_call_through_the_module_it_imported_from(session, tmp_path):
    files = {
        "pkg/a.py": "def compute(): pass\n",
        "pkg/b.py": "def compute(): pass\n",
        "tests/test_x.py": "from pkg.a import compute\ndef test_it():\n    compute()\n",
    }
    scan(session, tmp_path, files)
    linked = rows(session, "MATCH (:TestFunction)-[:TESTS]->(p:Function) RETURN p.file")
    assert linked == {("pkg/a.py",)}


def test_should_not_count_a_function_as_tested_by_an_import_alone(session, tmp_path):
    files = {"m.py": "def helper(): pass\n", "tests/test_x.py": "def test_it():\n    from m import helper\n"}
    scan(session, tmp_path, files)
    assert rows(session, FUNCTION_LINKS) == set()


def test_should_count_only_defined_production_functions_in_the_coverage_ratio(session, tmp_path):
    files = {
        "m.py": "def a(): pass\ndef b():\n    undefined()\n",
        "tests/test_m.py": "def test_a():\n    also_undefined()\n",
    }
    scan(session, tmp_path, files)
    from codescan_lib.mcp_tools.test_tools import get_test_coverage_ratio

    with patch("codescan_lib.mcp_tools.test_tools.q", lambda cypher, **p: [r.data() for r in session.run(cypher, **p)]):
        result = get_test_coverage_ratio()
    assert (result[0]["total_functions"], result[0]["tested_functions"]) == (2, 1)


def linked_files(session):
    return rows(session, "MATCH (:TestFunction)-[:TESTS]->(p:Function) RETURN p.file")


def test_should_not_resolve_an_imported_name_the_test_module_also_defines(session, tmp_path):
    test = "from pkg.a import compute\ndef compute(): return 2\ndef test_it(): assert compute() == 2\n"
    scan(session, tmp_path, {"pkg/a.py": "def compute(): return 1\n", "tests/test_x.py": test})
    assert linked_files(session) == set()


def test_should_not_let_an_import_in_a_class_body_reach_its_methods(session, tmp_path):
    test = (
        "from pkg.b import compute\nclass TestCalls:\n    from pkg.a import compute\n"
        "    def test_it(self): assert compute() == 2\n"
    )
    files = {"pkg/a.py": "def compute(): pass\n", "pkg/b.py": "def compute(): pass\n", "tests/test_x.py": test}
    scan(session, tmp_path, files)
    assert linked_files(session) == {("pkg/b.py",)}


def test_should_resolve_an_import_to_the_package_when_a_module_has_the_same_name(session, tmp_path):
    files = {
        "pkg/a.py": "def compute(): pass\n",
        "pkg/a/__init__.py": "def compute(): pass\n",
        "tests/test_x.py": "from pkg.a import compute\ndef test_it():\n    compute()\n",
    }
    scan(session, tmp_path, files)
    assert linked_files(session) == {("pkg/a/__init__.py",)}


AB = {"pkg/a.py": "def compute(): return 1\n", "pkg/b.py": "def compute(): return 2\n"}
IMPORT_AND_CALL = "from pkg.a import compute\ndef test_it(): assert compute() == 3\n"


def test_should_not_resolve_an_import_to_a_module_that_assigns_the_name_in_its_package(session, tmp_path):
    files = {**AB, "pkg/a/__init__.py": "compute = lambda: 3\n", "tests/test_x.py": IMPORT_AND_CALL}
    scan(session, tmp_path, files)
    assert linked_files(session) == set()


def test_should_not_resolve_an_import_to_a_module_that_also_assigns_the_name(session, tmp_path):
    files = {**AB, "pkg/a.py": AB["pkg/a.py"] + "compute = lambda: 3\n", "tests/test_x.py": IMPORT_AND_CALL}
    scan(session, tmp_path, files)
    assert linked_files(session) == set()


def test_should_not_let_an_import_in_an_outer_class_reach_methods_of_a_nested_class(session, tmp_path):
    test = (
        "from pkg.b import compute\nclass Outer:\n    from pkg.a import compute\n"
        "    class TestInner:\n        def test_it(self): assert compute() == 2\n"
    )
    scan(session, tmp_path, {**AB, "tests/test_x.py": test})
    assert linked_files(session) == {("pkg/b.py",)}


def test_should_not_resolve_an_import_the_module_rebinds_with_a_walrus_in_a_class_base(session, tmp_path):
    test = (
        "from pkg.a import compute\nclass C((compute := lambda: object)()):\n    pass\n"
        "def test_it(): assert compute() is object\n"
    )
    scan(session, tmp_path, {**AB, "tests/test_x.py": test})
    assert linked_files(session) == set()
