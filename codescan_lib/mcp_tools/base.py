"""
Base module for MCP tools.

This module contains common functionality used by all MCP tools.
"""
import os
import logging
import sys
from typing import List, Dict, Any
from contextlib import contextmanager

from dotenv import load_dotenv
from neo4j import GraphDatabase, basic_auth
from mcp.server.fastmcp import FastMCP

# --- Configuration & Setup ---
load_dotenv(".env", override=True)
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7600")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "strongpassword")
DEBUG_MCP = os.getenv("DEBUG_MCP", "false").lower() in ("true", "1", "yes")
LOG_FILE = os.getenv("LOG_FILE", "codescan_mcp_server.log")
MCP_SERVER_LOGGING_ENABLED = os.getenv("MCP_SERVER_LOGGING_ENABLED", "true").lower() in ("true", "1", "yes")

# --- Setup Logging ---
logger = logging.getLogger("codescan_mcp_server")

if MCP_SERVER_LOGGING_ENABLED:
    # Create logs directory if it doesn't exist
    os.makedirs("logs", exist_ok=True)
    log_file_path = os.path.join("logs", LOG_FILE)

    logger.setLevel(logging.DEBUG if DEBUG_MCP else logging.INFO)

    # Console handler - IMPORTANT: Use stderr instead of stdout
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(logging.DEBUG if DEBUG_MCP else logging.INFO)
    console_handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    ))
    logger.addHandler(console_handler)

    # File handler with rotation
    from logging.handlers import RotatingFileHandler
    file_handler = RotatingFileHandler(
        log_file_path,
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5
    )
    file_handler.setLevel(logging.DEBUG)  # Always log debug to file
    file_handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    ))
    logger.addHandler(file_handler)
    logger.info(f"Logging enabled. Level: {'DEBUG' if DEBUG_MCP else 'INFO'}. Log file: {os.path.abspath(log_file_path)}")
else:
    logger.setLevel(logging.CRITICAL + 1) # Effectively disable logging
    # Still need a basic print to stderr for this specific case, as logger is disabled.
    print("Logging is disabled via MCP_SERVER_LOGGING_ENABLED.", file=sys.stderr, flush=True)

# --- Initialize FastMCP ---
mcp = FastMCP("codescan_neo4j",
              instructions="Neo4j code graph analyzer for Python codebases")

# --- Neo4j Connection ---
driver = None

def verify_database_connection() -> Dict[str, Any]:
    """Verify connection to Neo4j database and return status."""
    connection_info = {
        "success": False,
        "uri": NEO4J_URI,
        "user": NEO4J_USER,
        "port": NEO4J_URI.split(":")[-1] if ":" in NEO4J_URI else "7687",
        "error": None
    }

    driver = None
    try:
        logger.info(f"Connecting to Neo4j at {NEO4J_URI}")
        driver = GraphDatabase.driver(
            NEO4J_URI,
            auth=basic_auth(NEO4J_USER, NEO4J_PASSWORD)
        )

        # Test connection with a simple query
        with driver.session() as session:
            result = session.run("RETURN 1 AS ok").single()
            if result and result.get("ok") == 1:
                connection_info["success"] = True
                logger.info(f"Successfully connected to Neo4j at {NEO4J_URI}")
            else:
                connection_info["error"] = "Connected but query returned unexpected result"
                logger.error(connection_info["error"])

    except Exception as e:
        error_msg = f"Failed to connect to Neo4j: {str(e)}"
        connection_info["error"] = error_msg
        logger.error(error_msg)

    finally:
        if driver:
            driver.close()

    return connection_info

# --- Initialize Neo4j Driver ---
initial_connection_status = verify_database_connection()
if initial_connection_status["success"]:
    try:
        driver = GraphDatabase.driver(
            NEO4J_URI,
            auth=basic_auth(NEO4J_USER, NEO4J_PASSWORD)
        )
    except Exception as e:
        logger.error(f"Failed to create Neo4j driver: {e}")

# --- Query Helper ---
def q(cypher: str, **params) -> List[Dict[str, Any]]:
    """Run a Cypher query and return list of dicts."""
    if MCP_SERVER_LOGGING_ENABLED and DEBUG_MCP:
        logger.debug(f"Executing Cypher Query: {cypher}")
        if params:
            logger.debug(f"Query Parameters: {params}")

    if driver is None:
        logger.error("Neo4j driver not available for query.")
        return []
    try:
        with driver.session() as s:
            results = [r.data() for r in s.run(cypher, **params)]
            if MCP_SERVER_LOGGING_ENABLED and DEBUG_MCP:
                logger.debug(f"Query returned {len(results)} rows.")
            return results
    except Exception as e:
        logger.error(f"Neo4j query error: {e}")
        return []

@contextmanager
def get_db_session():
    """
    Context manager for Neo4j database sessions.

    Creates a new driver and session, and ensures both are properly closed
    when the context is exited.

    Usage:
        with get_db_session() as session:
            result = session.run("MATCH (n) RETURN count(n)")
    """
    temp_driver = None
    try:
        temp_driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        session = temp_driver.session()
        yield session
    finally:
        if session:
            session.close()
        if temp_driver:
            temp_driver.close()
