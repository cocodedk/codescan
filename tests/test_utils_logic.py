"""Path and module classification helpers."""
from codescan_lib.utils import is_example_file, is_project_file, is_stdlib_module


def test_should_not_treat_names_ending_in_examples_as_example_dirs():
    assert not is_example_file("counterexamples/foo.py")


def test_should_treat_an_examples_directory_as_examples():
    assert is_example_file("pkg/examples/foo.py")


def test_should_recognise_stdlib_modules_inside_a_virtualenv():
    assert is_stdlib_module("json")


def test_should_not_treat_third_party_modules_as_stdlib():
    assert not is_stdlib_module("neo4j")


def test_should_reject_a_sibling_directory_sharing_the_project_prefix(tmp_path):
    sibling = tmp_path / "proj2" / "a.py"
    assert not is_project_file(str(sibling), str(tmp_path / "proj"))
