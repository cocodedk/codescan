"""Fixtures shared by the tests that scan into Neo4j."""
import pytest
from neo4j import GraphDatabase

from codescan_lib.constants import NEO4J_PASSWORD, NEO4J_URI, NEO4J_USER


@pytest.fixture
def session():
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    with driver.session() as s:
        yield s
    driver.close()


@pytest.fixture
def neo4j_test_session():
    """Create a test session for Neo4j."""
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    with driver.session() as session:
        yield session
    driver.close()
