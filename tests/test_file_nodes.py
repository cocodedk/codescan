import os
import tempfile
import shutil
import pytest
from neo4j import GraphDatabase

from codescan_lib.db_operations import clear_database
from codescan_lib.analysis import analyze_file, analyze_directory
from codescan_lib.constants import NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD

@pytest.fixture
def neo4j_test_session():
    """Create a test session for Neo4j."""
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    with driver.session() as session:
        yield session
    driver.close()

def test_file_node_creation(neo4j_test_session):
    """Test that File nodes are created for analyzed files."""
    # Create a temporary file with a class and function
    d = tempfile.mkdtemp()
    fpath = os.path.join(d, "test_file.py")
    with open(fpath, "w") as f:
        f.write('''
class TestClass:
    def test_method(self):
        return "test"

def standalone_function():
    return "standalone"
''')

    # Clear database and analyze the file
    clear_database(neo4j_test_session)
    analyze_file(fpath, neo4j_test_session, d)

    # Get the relative path that should be used
    rel_path = os.path.relpath(fpath, d)

    # Check if a File node was created
    file_node = neo4j_test_session.run(
        "MATCH (f:File {path: $path}) RETURN f",
        path=rel_path
    ).single()

    # Check if the File node is linked to the class
    file_to_class = neo4j_test_session.run(
        """
        MATCH (f:File {path: $path})-[:CONTAINS]->(c:Class {name: 'TestClass'})
        RETURN c
        """,
        path=rel_path
    ).single()

    # Check if the File node is linked to the standalone function
    file_to_function = neo4j_test_session.run(
        """
        MATCH (f:File {path: $path})-[:CONTAINS]->(func:Function {name: 'standalone_function'})
        RETURN func
        """,
        path=rel_path
    ).single()

    # Check if the class is linked to its method
    class_to_method = neo4j_test_session.run(
        """
        MATCH (c:Class {name: 'TestClass'})-[:CONTAINS]->(m:Function {name: 'TestClass.test_method'})
        RETURN m
        """,
    ).single()

    # Clean up
    shutil.rmtree(d)

    # Verify results
    assert file_node is not None, "File node was not created"
    assert file_to_class is not None, "File node is not linked to the class"
    assert file_to_function is not None, "File node is not linked to the standalone function"
    assert class_to_method is not None, "Class is not linked to its method"

def test_file_type_labeling(neo4j_test_session):
    """Test that File nodes have correct type labels."""
    # Create a temporary directory with production and test files
    d = tempfile.mkdtemp()

    # Create a production file
    prod_path = os.path.join(d, "production.py")
    with open(prod_path, "w") as f:
        f.write('def production_function(): pass\n')

    # Create a test file
    test_dir = os.path.join(d, "tests")
    os.makedirs(test_dir)
    test_path = os.path.join(test_dir, "test_module.py")
    with open(test_path, "w") as f:
        f.write('def test_function(): pass\n')

    # Clear database and analyze the directory
    clear_database(neo4j_test_session)
    analyze_directory(d, neo4j_test_session)

    # Get relative paths
    rel_prod_path = os.path.relpath(prod_path, d)
    rel_test_path = os.path.relpath(test_path, d)

    # Check if the production file has the correct label
    prod_file = neo4j_test_session.run(
        "MATCH (f:File {path: $path}) RETURN labels(f) AS labels",
        path=rel_prod_path
    ).single()

    # Check if the test file has the TestFile label
    test_file = neo4j_test_session.run(
        "MATCH (f:File:TestFile {path: $path}) RETURN labels(f) AS labels",
        path=rel_test_path
    ).single()

    # Clean up
    shutil.rmtree(d)

    # Verify results
    assert prod_file is not None, "Production file node was not created"
    assert 'File' in prod_file['labels'], "Production file missing File label"
    assert 'TestFile' not in prod_file['labels'], "Production file shouldn't have TestFile label"

    assert test_file is not None, "Test file node was not created"
    assert 'TestFile' in test_file['labels'], "Test file missing TestFile label"

def test_module_level_constants_linked_to_file(neo4j_test_session):
    """Test that module-level constants are linked to the File node."""
    # Create a temporary file with module-level constants
    d = tempfile.mkdtemp()
    fpath = os.path.join(d, "constants_file.py")
    with open(fpath, "w") as f:
        f.write('''
MODULE_LEVEL_CONSTANT = "module_level"

class TestClass:
    CLASS_LEVEL_CONSTANT = "class_level"

    def test_method(self):
        METHOD_LEVEL_CONSTANT = "method_level"
        return METHOD_LEVEL_CONSTANT
''')

    # Clear database and analyze the file
    clear_database(neo4j_test_session)
    analyze_file(fpath, neo4j_test_session, d)

    # Get the relative path
    rel_path = os.path.relpath(fpath, d)

    # Check if the module-level constant is linked to the File node
    file_to_constant = neo4j_test_session.run(
        """
        MATCH (f:File {path: $path})-[:CONTAINS]->(c:Constant {name: 'MODULE_LEVEL_CONSTANT'})
        RETURN c
        """,
        path=rel_path
    ).single()

    # Clean up
    shutil.rmtree(d)

    # Verify results
    assert file_to_constant is not None, "Module-level constant is not linked to the File node"
