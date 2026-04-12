import pytest
from codescan_mcp_server import (
    graph_summary, list_files, list_functions, list_classes, callees, callers,
    unresolved_references, uncalled_functions, most_called_functions, most_calling_functions,
    recursive_functions, classes_with_no_methods, functions_calling_references,
    classes_with_most_methods, function_call_arguments, rescan_codebase, file_contents,
    repetitive_constant_names
)

def test_graph_summary():
    result = graph_summary()
    assert isinstance(result, list)
    assert all('funcs' in r and 'classes' in r and 'calls' in r for r in result)

def test_list_files():
    result = list_files(random_string="dummy")
    assert isinstance(result, list)
    assert all('file' in r for r in result)

def test_list_functions_empty():
    result = list_functions(file="nonexistent.py")
    assert isinstance(result, list)
    assert result == []

def test_list_classes_empty():
    result = list_classes(file="nonexistent.py")
    assert isinstance(result, list)
    assert result == []

def test_callees_and_callers_empty():
    assert isinstance(callees("nonexistent"), list)
    assert isinstance(callers("nonexistent"), list)

def test_unresolved_references():
    result = unresolved_references()
    assert isinstance(result, list)
    for r in result:
        assert 'name' in r and 'first_seen_in' in r

def test_uncalled_functions():
    result = uncalled_functions()
    assert isinstance(result, list)
    for r in result:
        assert 'name' in r and 'file' in r

def test_most_called_functions():
    result = most_called_functions()
    assert isinstance(result, list)
    for r in result:
        assert 'name' in r and 'num_callers' in r

def test_most_calling_functions():
    result = most_calling_functions()
    assert isinstance(result, list)
    for r in result:
        assert 'name' in r and 'num_callees' in r

def test_recursive_functions():
    result = recursive_functions()
    assert isinstance(result, list)
    for r in result:
        assert 'name' in r and 'file' in r

def test_classes_with_no_methods():
    result = classes_with_no_methods()
    assert isinstance(result, list)
    for r in result:
        assert 'class' in r and 'file' in r

def test_functions_calling_references():
    result = functions_calling_references()
    assert isinstance(result, list)
    for r in result:
        assert 'name' in r and 'num_reference_calls' in r

def test_classes_with_most_methods():
    result = classes_with_most_methods()
    assert isinstance(result, list)
    for r in result:
        assert 'class' in r and 'num_methods' in r

def test_function_call_arguments_empty():
    result = function_call_arguments("nonexistent")
    assert isinstance(result, list)

@pytest.mark.skip(reason="This test takes too long to run")
def test_rescan_codebase_runs():
    result = rescan_codebase()
    assert isinstance(result, dict)
    assert 'success' in result and 'output' in result and 'error' in result

def test_file_contents_empty():
    result = file_contents(file="nonexistent.py")
    assert isinstance(result, dict)
    assert 'file' in result and 'contents' in result
    assert result['file'] == "nonexistent.py"
    assert isinstance(result['contents'], list)
    assert result['contents'] == []

def test_repetitive_constant_names():
    result = repetitive_constant_names()
    assert isinstance(result, list)
    for r in result:
        assert 'name' in r
        assert 'count' in r
        assert 'occurrences' in r
        assert isinstance(r['occurrences'], list)
        assert len(r['occurrences']) == r['count']
        for occurrence in r['occurrences']:
            assert 'value' in occurrence
            assert 'file' in occurrence
            assert 'line' in occurrence
            assert 'scope' in occurrence
