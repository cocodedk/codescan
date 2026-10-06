"""Which file an import reaches, and which imports the scan leaves out."""
import asyncio

import pytest
from import_helpers import cycles, edges, scan

from codescan_lib.analysis import analyze_file, finalize_graph
from codescan_lib.db_operations import clear_database


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
