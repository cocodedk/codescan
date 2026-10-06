"""The scan records IMPORTS_MODULE edges between project files; import_cycles lists the loops they form."""
import asyncio
import time

import pytest
from neo4j import GraphDatabase

from codescan_lib.analysis import analyze_file, finalize_graph
from codescan_lib.constants import NEO4J_PASSWORD, NEO4J_URI, NEO4J_USER
from codescan_lib.db_operations import clear_database
from codescan_lib.import_cycles import MAX_CYCLE_LENGTH
from codescan_lib.mcp_tools.flow_tools import import_cycles
from codescan_lib.stats_collector import StatsCollector

MANY = 1000


@pytest.fixture
def session():
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    with driver.session() as s:
        yield s
    driver.close()


def scan(session, tmp_path, files):
    """Scan a project given as {relative path: source}."""
    clear_database(session, quiet=True)
    stats = StatsCollector()
    for name, source in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source)
    for name in files:
        analyze_file(str(tmp_path / name), session, str(tmp_path), stats, defer_relationships=True)
    finalize_graph(session)


def edges(session):
    return sorted(
        (r["a"], r["b"]) for r in session.run(
            "MATCH (a:File)-[:IMPORTS_MODULE]->(b:File) RETURN a.path AS a, b.path AS b")
    )


def cycles():
    return [row["files"] for row in import_cycles(MANY)]


def test_should_report_two_files_importing_each_other_once(session, tmp_path):
    scan(session, tmp_path, {"a.py": "import b\n", "b.py": "import a\n"})
    assert cycles() == [["a.py", "b.py"]]


def test_should_report_the_length_of_a_cycle(session, tmp_path):
    scan(session, tmp_path, {"a.py": "import b\n", "b.py": "import a\n"})
    assert import_cycles()[0]["length"] == 2


def test_should_report_a_three_file_cycle_once_from_the_smallest_path(session, tmp_path):
    scan(session, tmp_path, {"c.py": "import a\n", "a.py": "import b\n", "b.py": "import c\n"})
    assert cycles() == [["a.py", "b.py", "c.py"]]


def test_should_report_the_other_direction_of_a_three_file_loop_as_its_own_cycle(session, tmp_path):
    files = {"a.py": "import b\nimport c\n", "b.py": "import c\nimport a\n", "c.py": "import a\nimport b\n"}
    scan(session, tmp_path, files)
    assert [c for c in cycles() if len(c) == 3] == [["a.py", "b.py", "c.py"], ["a.py", "c.py", "b.py"]]


def test_should_list_shorter_cycles_first(session, tmp_path):
    files = {"a.py": "import b\n", "b.py": "import c\n", "c.py": "import a\nimport d\n", "d.py": "import c\n"}
    scan(session, tmp_path, files)
    assert cycles() == [["c.py", "d.py"], ["a.py", "b.py", "c.py"]]


def test_should_respect_the_limit(session, tmp_path):
    files = {"a.py": "import b\nimport c\n", "b.py": "import a\n", "c.py": "import a\n"}
    scan(session, tmp_path, files)
    assert len(import_cycles(1)) == 1


def test_should_default_to_twenty_cycles(session, tmp_path):
    files = {"hub.py": "".join(f"import m{i}\n" for i in range(25))}
    files.update({f"m{i}.py": "import hub\n" for i in range(25)})
    scan(session, tmp_path, files)
    assert len(import_cycles()) == 20


def test_should_not_count_a_file_importing_itself(session, tmp_path):
    scan(session, tmp_path, {"a.py": "import a\n"})
    assert cycles() == []


def test_should_report_nothing_for_a_chain_of_imports(session, tmp_path):
    scan(session, tmp_path, {"a.py": "import b\n", "b.py": "import c\n", "c.py": "x = 1\n"})
    assert cycles() == []


def test_should_resolve_relative_imports_inside_a_package(session, tmp_path):
    files = {"pkg/__init__.py": "", "pkg/a.py": "from . import b\n", "pkg/b.py": "from .a import f\n"}
    scan(session, tmp_path, files)
    assert edges(session) == [("pkg/a.py", "pkg/b.py"), ("pkg/b.py", "pkg/a.py")]


def test_should_resolve_a_package_to_its_init_file(session, tmp_path):
    scan(session, tmp_path, {"pkg/__init__.py": "x = 1\n", "main.py": "import pkg\n"})
    assert edges(session) == [("main.py", "pkg/__init__.py")]


def test_should_resolve_a_name_imported_from_a_package_to_its_init_file(session, tmp_path):
    scan(session, tmp_path, {"pkg/__init__.py": "x = 1\n", "main.py": "from pkg import x\n"})
    assert edges(session) == [("main.py", "pkg/__init__.py")]


def test_should_prefer_the_package_over_a_module_of_the_same_name(session, tmp_path):
    scan(session, tmp_path, {"pkg/__init__.py": "", "pkg.py": "", "main.py": "import pkg\n"})
    assert edges(session) == [("main.py", "pkg/__init__.py")]


def test_should_resolve_a_dotted_import_to_the_submodule(session, tmp_path):
    scan(session, tmp_path, {"pkg/__init__.py": "", "pkg/sub.py": "", "main.py": "import pkg.sub\n"})
    assert edges(session) == [("main.py", "pkg/sub.py")]


def test_should_resolve_a_parent_relative_import(session, tmp_path):
    files = {"pkg/__init__.py": "", "pkg/top.py": "", "pkg/inner/__init__.py": "", "pkg/inner/m.py": "from ..top import f\n"}
    scan(session, tmp_path, files)
    assert edges(session) == [("pkg/inner/m.py", "pkg/top.py")]


def test_should_record_the_import_line(session, tmp_path):
    scan(session, tmp_path, {"a.py": "x = 1\n\nimport b\n", "b.py": ""})
    line = session.run("MATCH (:File)-[r:IMPORTS_MODULE]->(:File) RETURN r.line AS line").single()["line"]
    assert line == 3


def test_should_ignore_standard_library_and_third_party_imports(session, tmp_path):
    scan(session, tmp_path, {"a.py": "import os\nimport requests\nfrom json import loads\n", "b.py": ""})
    assert edges(session) == []


def test_should_ignore_a_standard_library_name_a_project_file_shares(session, tmp_path):
    scan(session, tmp_path, {"a.py": "import types\n", "types.py": ""})
    assert edges(session) == []


def test_should_ignore_imports_under_type_checking(session, tmp_path):
    source = "from typing import TYPE_CHECKING\nif TYPE_CHECKING:\n    import b\n"
    scan(session, tmp_path, {"a.py": source, "b.py": "import a\n"})
    assert (edges(session), cycles()) == ([("b.py", "a.py")], [])


def test_should_ignore_imports_under_typing_dot_type_checking(session, tmp_path):
    scan(session, tmp_path, {"a.py": "import typing\nif typing.TYPE_CHECKING:\n    import b\n", "b.py": ""})
    assert edges(session) == []


def test_should_count_an_import_in_the_else_of_type_checking(session, tmp_path):
    source = "from typing import TYPE_CHECKING\nif TYPE_CHECKING:\n    pass\nelse:\n    import b\n"
    scan(session, tmp_path, {"a.py": source, "b.py": ""})
    assert edges(session) == [("a.py", "b.py")]


def test_should_report_a_cycle_closed_by_a_function_level_import(session, tmp_path):
    scan(session, tmp_path, {"a.py": "import b\n", "b.py": "def f():\n    import a\n"})
    assert cycles() == [["a.py", "b.py"]]


def test_should_find_cycles_quickly_among_hundreds_of_densely_importing_files(session, tmp_path):
    files = {f"m{i}.py": f"import m{(i + 1) % 300}\nimport m{(i + 2) % 300}\nimport m{(i - 3) % 300}\n" for i in range(300)}
    scan(session, tmp_path, files)
    started = time.monotonic()
    rows = import_cycles(50)
    assert (len(rows), rows[0]["length"], time.monotonic() - started < 10) == (50, 3, True)


def test_should_not_report_a_loop_longer_than_the_search_bound(session, tmp_path):
    ring = MAX_CYCLE_LENGTH + 1
    scan(session, tmp_path, {f"m{i}.py": f"import m{(i + 1) % ring}\n" for i in range(ring)})
    assert cycles() == []


def test_should_report_a_loop_of_the_longest_searched_length(session, tmp_path):
    scan(session, tmp_path, {f"m{i}.py": f"import m{(i + 1) % MAX_CYCLE_LENGTH}\n" for i in range(MAX_CYCLE_LENGTH)})
    assert [len(c) for c in cycles()] == [MAX_CYCLE_LENGTH]


def test_should_stop_searching_once_the_limit_is_reached(session, tmp_path):
    width = 75
    files = {}
    for layer in range(4):
        imports = "".join(f"import l{(layer + 1) % 4}_{j}\n" for j in range(width))
        files.update({f"l{layer}_{i}.py": imports for i in range(width)})
    scan(session, tmp_path, files)
    started = time.monotonic()
    rows = import_cycles(20)
    assert (len(rows), rows[0]["length"], time.monotonic() - started < 5) == (20, 4, True)


def test_should_follow_a_star_import(session, tmp_path):
    scan(session, tmp_path, {"a.py": "from b import *\n", "b.py": "import a\n"})
    assert cycles() == [["a.py", "b.py"]]


@pytest.mark.parametrize("binding", ["x = 1", "def x():\n    pass", "class x:\n    pass", "from . import y as x", "import x"])
def test_should_import_a_name_the_package_binds_from_the_package_itself(session, tmp_path, binding):
    files = {"main.py": "from pkg import x\n", "pkg/__init__.py": binding + "\n", "pkg/x.py": "import main\n", "pkg/y.py": ""}
    scan(session, tmp_path, files)
    assert (("main.py", "pkg/__init__.py") in edges(session), cycles()) == (True, [])


def test_should_import_a_submodule_the_package_does_not_bind(session, tmp_path):
    scan(session, tmp_path, {"main.py": "from pkg import x\n", "pkg/__init__.py": "y = 1\n", "pkg/x.py": "import main\n"})
    assert cycles() == [["main.py", "pkg/x.py"]]


def test_should_still_import_the_submodule_for_a_plain_dotted_import(session, tmp_path):
    scan(session, tmp_path, {"main.py": "import pkg.x\n", "pkg/__init__.py": "x = 1\n", "pkg/x.py": ""})
    assert edges(session) == [("main.py", "pkg/x.py")]


def test_should_ignore_imports_under_an_aliased_type_checking(session, tmp_path):
    source = "from typing import TYPE_CHECKING as TC\nif TC:\n    import b\n"
    scan(session, tmp_path, {"a.py": source, "b.py": "import a\n"})
    assert cycles() == []


@pytest.mark.parametrize("header", ["import typing as t\nif t.TYPE_CHECKING:", "from typing_extensions import TYPE_CHECKING\nif TYPE_CHECKING:"])
def test_should_ignore_imports_under_a_typing_module_alias(session, tmp_path, header):
    scan(session, tmp_path, {"a.py": header + "\n    import b\n", "b.py": ""})
    assert edges(session) == []


def test_should_ignore_imports_under_type_checking_and_another_condition(session, tmp_path):
    source = "from typing import TYPE_CHECKING\nx = 1\nif TYPE_CHECKING and x:\n    import b\n"
    scan(session, tmp_path, {"a.py": source, "b.py": "import a\n"})
    assert cycles() == []


def test_should_count_imports_under_a_type_checking_that_is_not_typings(session, tmp_path):
    scan(session, tmp_path, {"config.py": "TYPE_CHECKING = True\n", "a.py": "import config\nif config.TYPE_CHECKING:\n    import b\n", "b.py": ""})
    assert ("a.py", "b.py") in edges(session)


def test_should_count_imports_under_a_type_checking_imported_from_elsewhere(session, tmp_path):
    scan(session, tmp_path, {"config.py": "TYPE_CHECKING = True\n", "a.py": "from config import TYPE_CHECKING\nif TYPE_CHECKING:\n    import b\n", "b.py": ""})
    assert ("a.py", "b.py") in edges(session)


def test_should_record_an_import_inside_a_skipped_dunder_method(session, tmp_path):
    scan(session, tmp_path, {"a.py": "class A:\n    def __init__(self):\n        import b\n", "b.py": "import a\n"})
    assert cycles() == [["a.py", "b.py"]]


def test_should_ignore_type_checking_imports_inside_a_skipped_dunder_method(session, tmp_path):
    source = "from typing import TYPE_CHECKING\nclass A:\n    def __init__(self):\n        if TYPE_CHECKING:\n            import b\n"
    scan(session, tmp_path, {"a.py": source, "b.py": ""})
    assert edges(session) == []


def test_should_resolve_absolute_imports_against_a_src_directory(session, tmp_path):
    files = {"src/pkg/__init__.py": "", "src/pkg/a.py": "import pkg.b\n", "src/pkg/b.py": "import pkg.a\n"}
    scan(session, tmp_path, files)
    assert cycles() == [["src/pkg/a.py", "src/pkg/b.py"]]


def test_should_prefer_a_top_level_module_over_the_same_name_under_src(session, tmp_path):
    scan(session, tmp_path, {"pkg.py": "", "src/pkg.py": "", "main.py": "import pkg\n"})
    assert edges(session) == [("main.py", "pkg.py")]


def test_should_drop_a_stale_edge_when_a_package_appears_later(session, tmp_path):
    clear_database(session, quiet=True)
    for name, source in (("pkg.py", ""), ("main.py", "import pkg\n"), ("pkg/__init__.py", "")):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(source)
        analyze_file(str(path), session, str(tmp_path))
    assert edges(session) == [("main.py", "pkg/__init__.py")]


def test_should_not_double_the_edges_when_a_file_is_scanned_twice(session, tmp_path):
    scan(session, tmp_path, {"a.py": "import b\n", "b.py": ""})
    analyze_file(str(tmp_path / "a.py"), session, str(tmp_path), defer_relationships=True)
    finalize_graph(session)
    assert edges(session) == [("a.py", "b.py")]


def test_should_not_let_a_package_import_itself_through_from_dot_import(session, tmp_path):
    scan(session, tmp_path, {"pkg/__init__.py": "from . import x\n", "pkg/x.py": "import pkg\n"})
    assert (edges(session), cycles()) == (
        [("pkg/__init__.py", "pkg/x.py"), ("pkg/x.py", "pkg/__init__.py")], [["pkg/__init__.py", "pkg/x.py"]])


def test_should_not_count_type_checking_shadowed_by_a_parameter(session, tmp_path):
    source = "from typing import TYPE_CHECKING\ndef f(TYPE_CHECKING=True):\n    if TYPE_CHECKING:\n        import b\n"
    scan(session, tmp_path, {"a.py": source, "b.py": "import a\n"})
    assert cycles() == [["a.py", "b.py"]]


def test_should_not_count_type_checking_shadowed_by_an_assignment_in_the_function(session, tmp_path):
    source = "from typing import TYPE_CHECKING\ndef f():\n    TYPE_CHECKING = True\n    if TYPE_CHECKING:\n        import b\n"
    scan(session, tmp_path, {"a.py": source, "b.py": "import a\n"})
    assert cycles() == [["a.py", "b.py"]]


def test_should_not_count_type_checking_shadowed_in_a_skipped_dunder_method(session, tmp_path):
    source = ("from typing import TYPE_CHECKING\nclass A:\n    def __init__(self, TYPE_CHECKING=True):\n"
              "        if TYPE_CHECKING:\n            import b\n")
    scan(session, tmp_path, {"a.py": source, "b.py": "import a\n"})
    assert cycles() == [["a.py", "b.py"]]


def test_should_not_count_a_binding_under_type_checking_as_the_package_binding_it(session, tmp_path):
    files = {"pkg/__init__.py": "from typing import TYPE_CHECKING\nif TYPE_CHECKING:\n    x = 1\n",
             "main.py": "from pkg import x\n", "pkg/x.py": "import main\n"}
    scan(session, tmp_path, files)
    assert cycles() == [["main.py", "pkg/x.py"]]


def test_should_count_a_binding_in_the_else_of_type_checking_as_the_package_binding_it(session, tmp_path):
    files = {"pkg/__init__.py": "from typing import TYPE_CHECKING\nif TYPE_CHECKING:\n    pass\nelse:\n    x = 1\n",
             "main.py": "from pkg import x\n", "pkg/x.py": "import main\n"}
    scan(session, tmp_path, files)
    assert cycles() == []


def test_should_take_the_names_a_star_import_binds_as_bound_by_the_package(session, tmp_path):
    files = {"pkg/__init__.py": "from .config import *\n", "pkg/config.py": "x = 1\n",
             "main.py": "from pkg import x\n", "pkg/x.py": "import main\n"}
    scan(session, tmp_path, files)
    assert (("main.py", "pkg/__init__.py") in edges(session), cycles()) == (True, [])


def test_should_import_the_submodule_when_the_star_import_does_not_bind_the_name(session, tmp_path):
    files = {"pkg/__init__.py": "from .config import *\n", "pkg/config.py": "y = 1\n",
             "main.py": "from pkg import x\n", "pkg/x.py": "import main\n"}
    scan(session, tmp_path, files)
    assert cycles() == [["main.py", "pkg/x.py"]]


def test_should_keep_the_test_file_import_nodes(session, tmp_path):
    scan(session, tmp_path, {"tests/test_a.py": "import a\n\ndef test_x():\n    pass\n", "a.py": ""})
    imports = session.run("MATCH (i:Import) RETURN count(i) AS n").single()["n"]
    assert (imports, edges(session)) == (1, [("tests/test_a.py", "a.py")])


def test_should_register_the_tool_with_the_server():
    import codescan_mcp_server  # noqa: F401  (importing registers every tool)
    from codescan_lib.mcp_tools.base import mcp

    assert "import_cycles" in {tool.name for tool in asyncio.run(mcp.list_tools())}
