import os
import shutil
import tempfile

from codescan_lib.analysis import analyze_file
from codescan_lib.db_operations import clear_database


def test_module_level_constant(neo4j_test_session):
    """Test that module-level constants are detected."""
    # Create a temporary file with a module-level constant
    d = tempfile.mkdtemp()
    fpath = os.path.join(d, "constants_mod.py")
    with open(fpath, "w") as f:
        f.write('MAXRETRIES = 3\n')  # Not a constant (no underscore)
        f.write('MAX_RETRY_COUNT = 5\n')  # This is a constant

    # Clear database and analyze the file
    clear_database(neo4j_test_session)
    analyze_file(fpath, neo4j_test_session, d)

    # Check if the constant was added to the database
    result = neo4j_test_session.run(
        "MATCH (c:Constant {name: 'MAX_RETRY_COUNT'}) RETURN c.value, c.type, c.scope"
    ).single()

    # Clean up
    shutil.rmtree(d)

    # Verify results
    assert result is not None
    assert result["c.value"] == "5"
    assert result["c.type"] == "int"
    assert result["c.scope"] == "module"

    # Verify that non-constant was not added
    non_constant = neo4j_test_session.run(
        "MATCH (c:Constant {name: 'MAXRETRIES'}) RETURN c"
    ).single()
    assert non_constant is None


def test_class_level_constant(neo4j_test_session):
    """Test that class-level constants are detected."""
    # Create a temporary file with a class-level constant
    d = tempfile.mkdtemp()
    fpath = os.path.join(d, "constants_class.py")
    with open(fpath, "w") as f:
        f.write('''
class Config:
    DEBUG = True  # Not a constant (no underscore)
    DEFAULTTIMEOUT = 30  # Not a constant (no underscore)
    MAX_CONNECTION_RETRIES = 3  # This is a constant
''')

    # Clear database and analyze the file
    clear_database(neo4j_test_session)
    analyze_file(fpath, neo4j_test_session, d)

    # Check if the constant was added to the database
    result = neo4j_test_session.run(
        "MATCH (c:Constant {name: 'MAX_CONNECTION_RETRIES'}) RETURN c.value, c.type, c.scope"
    ).single()

    # Check relationship to class
    relationship = neo4j_test_session.run(
        """
        MATCH (class:Class {name: 'Config'})-[:DEFINES]->(c:Constant {name: 'MAX_CONNECTION_RETRIES'})
        RETURN class.name
        """
    ).single()

    # Clean up
    shutil.rmtree(d)

    # Verify results
    assert result is not None
    assert result["c.value"] == "3"
    assert result["c.type"] == "int"
    assert result["c.scope"] == "class"

    # Verify relationship
    assert relationship is not None
    assert relationship["class.name"] == "Config"

    # Verify that non-constants were not added
    non_constants = neo4j_test_session.run(
        "MATCH (c:Constant) WHERE c.name IN ['DEBUG', 'DEFAULTTIMEOUT'] RETURN count(c) as count"
    ).single()
    assert non_constants["count"] == 0


def test_function_level_constant(neo4j_test_session):
    """Test that function-level constants are detected."""
    # Create a temporary file with a function-level constant
    d = tempfile.mkdtemp()
    fpath = os.path.join(d, "constants_func.py")
    with open(fpath, "w") as f:
        f.write('''
def process_data():
    retry_count = 3  # Not a constant (lowercase)
    MAXITEMS = 30  # Not a constant (no underscore)
    MAX_ITEMS_PER_PAGE = 50  # This is a constant
    return MAX_ITEMS_PER_PAGE
''')

    # Clear database and analyze the file
    clear_database(neo4j_test_session)
    analyze_file(fpath, neo4j_test_session, d)

    # Check if the constant was added to the database
    result = neo4j_test_session.run(
        "MATCH (c:Constant {name: 'MAX_ITEMS_PER_PAGE'}) RETURN c.value, c.type, c.scope"
    ).single()

    # Check relationship to function
    relationship = neo4j_test_session.run(
        """
        MATCH (func:Function {name: 'process_data'})-[:DEFINES]->(c:Constant {name: 'MAX_ITEMS_PER_PAGE'})
        RETURN func.name
        """
    ).single()

    # Clean up
    shutil.rmtree(d)

    # Verify results
    assert result is not None
    assert result["c.value"] == "50"
    assert result["c.type"] == "int"
    assert result["c.scope"] == "function"

    # Verify relationship
    assert relationship is not None
    assert relationship["func.name"] == "process_data"

    # Verify that non-constants were not added
    non_constants = neo4j_test_session.run(
        "MATCH (c:Constant) WHERE c.name IN ['retry_count', 'MAXITEMS'] RETURN count(c) as count"
    ).single()
    assert non_constants["count"] == 0
