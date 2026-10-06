"""The scan records IMPORTS_MODULE edges between project files; import_cycles lists the loops they form."""
import time

from import_helpers import cycles, edges, scan

from codescan_lib.import_cycles import MAX_CYCLE_LENGTH
from codescan_lib.mcp_tools.flow_tools import import_cycles


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
