import builtins
import os

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Neo4j connection details
NEO4J_HOST = os.getenv("NEO4J_HOST", "localhost")
NEO4J_PORT_BOLT = os.getenv("NEO4J_PORT_BOLT", "7600")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "password")
NEO4J_URI = f"bolt://{NEO4J_HOST}:{NEO4J_PORT_BOLT}"

# Test detection configuration
TEST_DIR_PATTERNS = os.getenv("TEST_DIR_PATTERNS", "tests/,test/,testing/").split(",")
TEST_FILE_PATTERNS = os.getenv("TEST_FILE_PATTERNS", "test_*.py,*_test.py").split(",")
TEST_FUNCTION_PREFIXES = os.getenv("TEST_FUNCTION_PREFIXES", "test_").split(",")
TEST_CLASS_PATTERNS = os.getenv("TEST_CLASS_PATTERNS", "Test*,*Test").split(",")

# Directories to ignore during analysis
IGNORE_DIRS = ['.git', '__pycache__', 'drp_venv', 'venv', '.venv', 'node_modules', 'build', 'dist', '.cache']

# Set of built-in functions to ignore
BUILTIN_FUNCTIONS = set(dir(builtins))
