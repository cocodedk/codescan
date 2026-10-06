import os

from neo4j import Driver, GraphDatabase, Session

from .constants import (
    COLOR_FILE_CONTAINS,
    NEO4J_HOST,
    NEO4J_PASSWORD,
    NEO4J_URI,
    NEO4J_USER,
    SCOPE_MODULE,
)


def clear_database(session: Session, quiet: bool = False) -> None:
    """
    Clear all nodes and relationships in the database.

    Args:
        session: Neo4j database session
        quiet: Whether to suppress output
    """
    if not quiet:
        print("Clearing database...")
    session.run("MATCH (n) DETACH DELETE n")

def get_db_session() -> Session:
    """Create and return a Neo4j database session."""
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    return driver.session()

def close_db_connection(driver: Driver) -> None:
    """Close the Neo4j database connection."""
    driver.close()

def print_db_info(quiet: bool = False) -> None:
    """
    Print database connection information and usage instructions.

    Args:
        quiet: Whether to suppress output
    """
    if quiet:
        return

    print("\n=== Neo4j Graph Database Info ===")
    print(f"- Neo4j Browser: http://{NEO4J_HOST}:{os.getenv('NEO4J_PORT_HTTP', '7400')}")
    print("\nUseful Cypher queries:")
    print("- Show all nodes: MATCH (n) RETURN n")
    print("- Find functions by line: MATCH (f:Function) WHERE f.line > 100 RETURN f")
    print("- Show relationships: MATCH (n)-[r]->(m) RETURN n, r, m")
    print("- Show calls at specific line: MATCH ()-[r:CALLS {line: 42}]->() RETURN r")
    print("- Find long functions: MATCH (f:Function) RETURN f.name, f.file, f.length ORDER BY f.length DESC LIMIT 10")
    print("=== End of Database Info ===")

# The lookups every scan repeats: each MATCH by these properties would
# otherwise scan every node with the label.
INDEXES = (
    "CREATE INDEX IF NOT EXISTS FOR (f:Function) ON (f.name, f.file)",
    "CREATE INDEX IF NOT EXISTS FOR (r:ReferenceFunction) ON (r.name)",
    "CREATE INDEX IF NOT EXISTS FOR (c:Class) ON (c.name, c.file)",
    "CREATE INDEX IF NOT EXISTS FOR (c:Constant) ON (c.name, c.file)",
    "CREATE INDEX IF NOT EXISTS FOR (f:File) ON (f.path)",
)


def ensure_indexes(session: Session) -> None:
    """Create the indexes a scan's lookups need, if they are missing."""
    for statement in INDEXES:
        session.run(statement)


def link_file_contents(session: Session, rel_path: str) -> None:
    """Connect a File node to the classes, functions and constants defined in it."""
    session.run(
        "MATCH (f:File {path: $path}) MATCH (c:Class {file: $path}) MERGE (f)-[:CONTAINS {color: $color}]->(c)",
        path=rel_path,
        color=COLOR_FILE_CONTAINS,
    )
    # Functions that are not methods
    session.run(
        """
        MATCH (f:File {path: $path})
        MATCH (func:Function {file: $path})
        WHERE func.is_reference = false AND NOT EXISTS {
          MATCH (c:Class)-[:CONTAINS]->(func)
        }
        MERGE (f)-[:CONTAINS {color: $color}]->(func)
        """,
        path=rel_path,
        color=COLOR_FILE_CONTAINS,
    )
    # Constants that are not inside a class or function
    session.run(
        f"""
        MATCH (f:File {{path: $path}})
        MATCH (const:Constant {{file: $path, scope: '{SCOPE_MODULE}'}})
        MERGE (f)-[:CONTAINS {{color: $color}}]->(const)
        """,
        path=rel_path,
        color=COLOR_FILE_CONTAINS,
    )
