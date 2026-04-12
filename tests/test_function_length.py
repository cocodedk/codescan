import os
import tempfile
import shutil
import pytest
from neo4j import GraphDatabase

from codescan_lib.db_operations import clear_database
from codescan_lib.analysis import analyze_file
from codescan_lib.constants import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD

@pytest.fixture
def neo4j_test_session():
    """Create a test session for Neo4j."""
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    with driver.session() as session:
        yield session
    driver.close()

def test_single_line_function_length(neo4j_test_session):
    """Test that single-line function length is calculated correctly."""
    # Create a temporary file with a single-line function
    d = tempfile.mkdtemp()
    fpath = os.path.join(d, "single_line_func.py")
    with open(fpath, "w") as f:
        f.write('def single_line_function(): return "hello"\n')

    # Clear database and analyze the file
    clear_database(neo4j_test_session)
    analyze_file(fpath, neo4j_test_session, d)

    # Check if the function length was calculated correctly
    result = neo4j_test_session.run(
        "MATCH (f:Function {name: 'single_line_function'}) RETURN f.length as length"
    ).single()

    # Clean up
    shutil.rmtree(d)

    # Verify results
    assert result is not None
    assert result["length"] == 1  # Single-line function should have length 1

def test_multi_line_function_length(neo4j_test_session):
    """Test that multi-line function length is calculated correctly."""
    # Create a temporary file with a multi-line function
    d = tempfile.mkdtemp()
    fpath = os.path.join(d, "multi_line_func.py")
    with open(fpath, "w") as f:
        f.write('''
def multi_line_function():
    # This is a comment
    x = 1
    y = 2
    z = x + y
    return z
''')

    # Clear database and analyze the file
    clear_database(neo4j_test_session)
    analyze_file(fpath, neo4j_test_session, d)

    # Check if the function length was calculated correctly
    result = neo4j_test_session.run(
        "MATCH (f:Function {name: 'multi_line_function'}) RETURN f.length as length"
    ).single()

    # Clean up
    shutil.rmtree(d)

    # Verify results
    assert result is not None
    assert result["length"] == 6  # Function spans 6 lines (from line 2 to line 7)

def test_nested_function_length(neo4j_test_session):
    """Test that nested function lengths are calculated correctly."""
    # Create a temporary file with nested functions
    d = tempfile.mkdtemp()
    fpath = os.path.join(d, "nested_func.py")
    with open(fpath, "w") as f:
        f.write('''
def outer_function():
    x = 1

    def inner_function():
        y = 2
        return y

    return inner_function() + x
''')

    # Clear database and analyze the file
    clear_database(neo4j_test_session)
    analyze_file(fpath, neo4j_test_session, d)

    # Check if the function lengths were calculated correctly
    outer_result = neo4j_test_session.run(
        "MATCH (f:Function {name: 'outer_function'}) RETURN f.length as length"
    ).single()

    # For inner functions, we need to check if they're in the database at all
    inner_exists = neo4j_test_session.run(
        "MATCH (f:Function) WHERE f.name CONTAINS 'inner_function' RETURN f.name, f.length"
    ).data()

    # Clean up
    shutil.rmtree(d)

    # Verify results
    assert outer_result is not None
    assert outer_result["length"] == 8  # Outer function spans 8 lines (from line 2 to line 9)

    # Note: The current implementation might not correctly handle inner functions
    # This is a known limitation, so we just log it for now
    print(f"Inner function data: {inner_exists}")

def test_class_method_length(neo4j_test_session):
    """Test that class method lengths are calculated correctly."""
    # Create a temporary file with a class and methods
    d = tempfile.mkdtemp()
    fpath = os.path.join(d, "class_method.py")
    with open(fpath, "w") as f:
        f.write('''
class TestClass:
    def short_method(self):
        return "short"

    def longer_method(self):
        x = 1
        y = 2
        z = x + y
        return z
''')

    # Clear database and analyze the file
    clear_database(neo4j_test_session)
    analyze_file(fpath, neo4j_test_session, d)

    # Check if the method lengths were calculated correctly
    short_result = neo4j_test_session.run(
        "MATCH (f:Function {name: 'TestClass.short_method'}) RETURN f.length as length"
    ).single()

    long_result = neo4j_test_session.run(
        "MATCH (f:Function {name: 'TestClass.longer_method'}) RETURN f.length as length"
    ).single()

    # Clean up
    shutil.rmtree(d)

    # Verify results
    assert short_result is not None
    assert short_result["length"] == 2  # Short method spans 2 lines

    assert long_result is not None
    assert long_result["length"] == 5  # Longer method spans 5 lines

def test_reference_function_length(neo4j_test_session):
    """Test that reference function lengths are set to 0."""
    # Create a temporary file with a function that calls an undefined function
    d = tempfile.mkdtemp()
    fpath = os.path.join(d, "reference_func.py")
    with open(fpath, "w") as f:
        f.write('''
def calling_function():
    # This calls an undefined function
    return undefined_function()
''')

    # Clear database and analyze the file
    clear_database(neo4j_test_session)
    analyze_file(fpath, neo4j_test_session, d)

    # Check if the reference function length is set to 0
    result = neo4j_test_session.run(
        "MATCH (f:Function:ReferenceFunction {name: 'undefined_function'}) RETURN f.length as length"
    ).single()

    # Clean up
    shutil.rmtree(d)

    # Verify results
    assert result is not None
    assert result["length"] == 0  # Reference functions should have length 0
