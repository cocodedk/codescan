import os
import shutil
import tempfile

import pytest
from neo4j import GraphDatabase

from codescan_lib import analyze_directory, analyze_file, clear_database


@pytest.fixture(scope="module")
def neo4j_test_session():
    uri = os.getenv("NEO4J_URI", "bolt://localhost:7600")
    user = os.getenv("NEO4J_USER", "neo4j")
    password = os.getenv("NEO4J_PASSWORD", "demodemo")
    driver = GraphDatabase.driver(uri, auth=(user, password))
    with driver.session() as session:
        yield session
    driver.close()

@pytest.fixture
def temp_pyfile():
    d = tempfile.mkdtemp()
    fpath = os.path.join(d, "testmod.py")
    with open(fpath, "w") as f:
        f.write("""
class A:
    def foo(self):
        pass

def bar():
    print('hi')
    foo()
""")
    yield fpath, d
    shutil.rmtree(d)

def test_clear_database(neo4j_test_session):
    clear_database(neo4j_test_session)
    result = neo4j_test_session.run("MATCH (n) RETURN count(n) AS cnt").single()
    assert result["cnt"] == 0

def test_analyze_file_nodes_and_edges(neo4j_test_session, temp_pyfile):
    fpath, basedir = temp_pyfile
    clear_database(neo4j_test_session)
    analyze_file(fpath, neo4j_test_session, basedir)
    # Class node
    res = neo4j_test_session.run("MATCH (c:Class {name:'A'}) RETURN c").single()
    assert res is not None
    # Function node
    res = neo4j_test_session.run("MATCH (f:Function {name:'bar'}) RETURN f").single()
    assert res is not None
    # Contains edge
    res = neo4j_test_session.run("MATCH (c:Class)-[:CONTAINS]->(f:Function) RETURN c,f").single()
    assert res is not None

def test_reference_function(neo4j_test_session, temp_pyfile):
    fpath, basedir = temp_pyfile
    clear_database(neo4j_test_session)
    analyze_file(fpath, neo4j_test_session, basedir)
    res = neo4j_test_session.run("MATCH (f:Function:ReferenceFunction {name:'foo'}) RETURN f").single()
    assert res is not None

def test_builtin_and_stdlib_skipped(neo4j_test_session, temp_pyfile):
    fpath, basedir = temp_pyfile
    clear_database(neo4j_test_session)
    analyze_file(fpath, neo4j_test_session, basedir)
    # print is builtin, should not be a node
    res = neo4j_test_session.run("MATCH (f:Function {name:'print'}) RETURN f").single()
    assert res is None

def test_relative_path_storage(neo4j_test_session, temp_pyfile):
    fpath, basedir = temp_pyfile
    clear_database(neo4j_test_session)
    analyze_file(fpath, neo4j_test_session, basedir)
    res = neo4j_test_session.run("MATCH (f:Function {name:'bar'}) RETURN f.file AS file").single()
    assert res is not None
    assert not os.path.isabs(res["file"])

def test_ignore_dirs(neo4j_test_session):
    # Create a file in an ignored dir
    d = tempfile.mkdtemp()
    ignore_dir = os.path.join(d, "venv")
    os.makedirs(ignore_dir)
    fpath = os.path.join(ignore_dir, "foo.py")
    with open(fpath, "w") as f:
        f.write("def foo(): pass\n")
    clear_database(neo4j_test_session)
    analyze_directory(d, neo4j_test_session)
    res = neo4j_test_session.run("MATCH (f:Function {name:'foo'}) RETURN f").single()
    shutil.rmtree(d)
    assert res is None

def test_syntax_error_handling(neo4j_test_session):
    d = tempfile.mkdtemp()
    fpath = os.path.join(d, "bad.py")
    with open(fpath, "w") as f:
        f.write("def bad(:\n")
    clear_database(neo4j_test_session)
    # Should not raise
    analyze_file(fpath, neo4j_test_session, d)
    shutil.rmtree(d)

def test_unicode_decode_error_handling(neo4j_test_session):
    d = tempfile.mkdtemp()
    fpath = os.path.join(d, "bad.py")
    with open(fpath, "wb") as f:
        f.write(b"\xff\xfe\xfd\xfc\xfb\xfa")
    clear_database(neo4j_test_session)
    # Should not raise
    analyze_file(fpath, neo4j_test_session, d)
    shutil.rmtree(d)
