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

# Edge colours used when writing relationships to the graph
COLOR_CALLS = "#FF9800"
COLOR_CLASS_CONTAINS = "#9C27B0"
COLOR_DEFINES = "#E91E63"
COLOR_IMPORTS = "#4CAF50"
COLOR_TESTS = "#3F51B5"
COLOR_FILE_CONTAINS = "#2196F3"
COLOR_IMPORTS_MODULE = "#00BCD4"

TYPE_CHECKING_NAME = "TYPE_CHECKING"
TYPE_CHECKING_MODULES = {"typing", "typing_extensions"}  # the modules whose TYPE_CHECKING is the real one

# How a TESTS edge was found
TEST_METHOD_NAMING = "naming_pattern"
TEST_METHOD_CALL = "call"

# Where the analyzer is while it walks a file; stored on Constant nodes as `scope`
SCOPE_MODULE = "module"
SCOPE_CLASS = "class"
SCOPE_FUNCTION = "function"

# The shape of a call, stored on CALLS edges as `kind`
BARE_CALL = "bare"
SELF_CALL = "self"
ATTR_CALL = "attr"

# Receivers that make `receiver.name()` a self call
RECEIVER_SELF = "self"
RECEIVER_CLS = "cls"
SELF_NAMES = (RECEIVER_SELF, RECEIVER_CLS)

# What kind of file a scanned file is (the keys of the by-type counts)
FILE_TYPE_PRODUCTION = "production"
FILE_TYPE_TEST = "test"
FILE_TYPE_EXAMPLE = "example"

# The element counts a scan reports
STAT_CLASSES = "classes"
STAT_FUNCTIONS = "functions"
STAT_CONSTANTS = "constants"
STAT_CALLS = "calls"
STAT_IMPORTS = "imports"
STAT_REFERENCE_FUNCTIONS = "reference_functions"
STAT_TEST_FUNCTIONS = "test_functions"
STAT_TEST_CLASSES = "test_classes"

# Decorators known to return the class they decorate (by the module that defines them): a call to such a class builds it
CLASS_PRESERVING_DECORATORS = {
    "dataclasses.dataclass", "functools.total_ordering", "typing.final", "typing.runtime_checkable", "enum.unique",
}
