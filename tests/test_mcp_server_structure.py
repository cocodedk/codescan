"""
Test the modular MCP server structure.
"""
import importlib


def test_tool_imports():
    """Test that all tools can be imported from their modules."""
    # Core tools
    # Call graph tools
    from codescan_lib.mcp_tools.call_graph import (
        callees,
        callers,
        function_call_arguments,
        functions_calling_references,
        most_called_functions,
        most_calling_functions,
        recursive_functions,
        transitive_calls,
        uncalled_functions,
        unresolved_references,
    )

    # Class tools
    from codescan_lib.mcp_tools.class_tools import (
        classes_with_most_methods,
        classes_with_no_methods,
    )

    # Constant tools
    from codescan_lib.mcp_tools.constant_tools import (
        repetitive_constant_names,
        repetitive_constants,
    )
    from codescan_lib.mcp_tools.core import (
        get_connection_status_tool,
        graph_summary,
        rescan_codebase,
    )

    # File tools
    from codescan_lib.mcp_tools.file_tools import (
        file_contents,
        list_classes,
        list_files,
        list_functions,
    )

    # Test tools
    from codescan_lib.mcp_tools.test_tools import (
        functions_tested_by,
        get_example_files,
        get_test_coverage_ratio,
        get_test_detection_config,
        get_test_files,
        get_tests_for_function,
        list_example_classes,
        list_example_functions,
        list_test_classes,
        list_test_functions,
        untested_classes,
        untested_functions,
    )

    # Import main MCP server - should import all tools

    # Verify all expected functions are callable
    assert callable(get_connection_status_tool)
    assert callable(graph_summary)
    assert callable(rescan_codebase)
    assert callable(list_files)
    assert callable(file_contents)
    assert callable(list_functions)
    assert callable(list_classes)
    assert callable(callees)
    assert callable(callers)
    assert callable(unresolved_references)
    assert callable(uncalled_functions)
    assert callable(most_called_functions)
    assert callable(most_calling_functions)
    assert callable(recursive_functions)
    assert callable(functions_calling_references)
    assert callable(function_call_arguments)
    assert callable(transitive_calls)
    assert callable(classes_with_no_methods)
    assert callable(classes_with_most_methods)
    assert callable(repetitive_constants)
    assert callable(repetitive_constant_names)
    assert callable(list_test_functions)
    assert callable(list_example_functions)
    assert callable(list_test_classes)
    assert callable(list_example_classes)
    assert callable(get_test_files)
    assert callable(get_example_files)
    assert callable(get_test_detection_config)
    assert callable(untested_functions)
    assert callable(get_test_coverage_ratio)
    assert callable(functions_tested_by)
    assert callable(get_tests_for_function)
    assert callable(untested_classes)

def test_module_structure():
    """Test that the module structure is organized as expected."""
    # Make sure each module exists
    modules = [
        "codescan_lib.mcp_tools",
        "codescan_lib.mcp_tools.base",
        "codescan_lib.mcp_tools.core",
        "codescan_lib.mcp_tools.file_tools",
        "codescan_lib.mcp_tools.call_graph",
        "codescan_lib.mcp_tools.class_tools",
        "codescan_lib.mcp_tools.constant_tools",
        "codescan_lib.mcp_tools.test_tools"
    ]

    for module_name in modules:
        module = importlib.import_module(module_name)
        assert module is not None, f"Module {module_name} not found"
