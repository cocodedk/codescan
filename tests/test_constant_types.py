import os
import shutil
import tempfile

from codescan_lib.analysis import analyze_directory, analyze_file
from codescan_lib.db_operations import clear_database


def test_complex_constant_types(neo4j_test_session):
    """Test that constants with complex types are correctly processed."""
    # Create a temporary file with constants of different types
    d = tempfile.mkdtemp()
    fpath = os.path.join(d, "constants_types.py")
    with open(fpath, "w") as f:
        f.write('''
# String constant
DEFAULTMESSAGE = "Hello, World!"  # Not a constant (no underscore)
ERROR_MESSAGE = "An error occurred"  # This is a constant

# List constant
ALLOWED_TYPES = ["jpg", "png", "gif"]  # This is a constant

# Dict constant
HTTP_STATUS_CODES = {
    "OK": 200,
    "NOT_FOUND": 404,
    "SERVER_ERROR": 500
}  # This is a constant

# Tuple constant
SCREENDIMENSIONS = (1920, 1080)  # Not a constant (no underscore)
VALID_DIMENSIONS = (800, 600, 1024, 768)  # This is a constant
''')

    # Clear database and analyze the file
    clear_database(neo4j_test_session)
    analyze_file(fpath, neo4j_test_session, d)

    # Check if constants were added to the database
    results = neo4j_test_session.run(
        """
        MATCH (c:Constant)
        WHERE c.name IN ['ERROR_MESSAGE', 'ALLOWED_TYPES', 'HTTP_STATUS_CODES', 'VALID_DIMENSIONS']
        RETURN c.name, c.value, c.type
        """
    ).data()

    # Clean up
    shutil.rmtree(d)

    # Verify results
    assert len(results) == 4

    # Create a dictionary for easier assertion
    constants = {r["c.name"]: (r["c.value"], r["c.type"]) for r in results}

    # Verify each constant
    assert "ERROR_MESSAGE" in constants
    assert constants["ERROR_MESSAGE"][1] == "str"

    assert "ALLOWED_TYPES" in constants
    assert constants["ALLOWED_TYPES"][1] == "list"

    assert "HTTP_STATUS_CODES" in constants
    assert constants["HTTP_STATUS_CODES"][1] == "dict"

    assert "VALID_DIMENSIONS" in constants
    assert constants["VALID_DIMENSIONS"][1] == "tuple"

    # Verify that non-constants were not added
    non_constants = neo4j_test_session.run(
        "MATCH (c:Constant) WHERE c.name IN ['DEFAULTMESSAGE', 'SCREENDIMENSIONS'] RETURN count(c) as count"
    ).single()
    assert non_constants["count"] == 0


def test_repetitive_constants(neo4j_test_session):
    """Test detection of repetitive constants."""
    # Create temporary files with the same constant values in different places
    d = tempfile.mkdtemp()

    # File 1
    fpath1 = os.path.join(d, "constants1.py")
    with open(fpath1, "w") as f:
        f.write('''
MAX_RETRY_COUNT = 3
DEFAULT_TIMEOUT_MS = 5000
''')

    # File 2
    fpath2 = os.path.join(d, "constants2.py")
    with open(fpath2, "w") as f:
        f.write('''
class Config:
    CONNECTIONRETRIES = 3  # Not a constant (no underscore)
    RETRYLIMIT = 3  # Not a constant (no underscore)
    REQUEST_TIMEOUT_MS = 5000  # This is a constant
''')

    # File 3
    fpath3 = os.path.join(d, "constants3.py")
    with open(fpath3, "w") as f:
        f.write('''
def process():
    PROCESS_TIMEOUT_MS = 5000  # This is a constant
    return True
''')

    # Clear database and analyze the directory
    clear_database(neo4j_test_session)
    analyze_directory(d, neo4j_test_session)

    # Check for constants with the same value
    same_value_3 = neo4j_test_session.run(
        """
        MATCH (c:Constant)
        WHERE c.value = "3"
        RETURN c.name
        """
    ).data()

    same_value_5000 = neo4j_test_session.run(
        """
        MATCH (c:Constant)
        WHERE c.value = "5000"
        RETURN c.name
        """
    ).data()

    # Clean up
    shutil.rmtree(d)

    # Verify results
    assert len(same_value_3) == 1
    assert len(same_value_5000) == 3

    # Check that we found the expected constants with value 3
    names_3 = [r["c.name"] for r in same_value_3]
    assert "MAX_RETRY_COUNT" in names_3

    # Check that we found the expected constants with value 5000
    names_5000 = [r["c.name"] for r in same_value_5000]
    assert "DEFAULT_TIMEOUT_MS" in names_5000
    assert "REQUEST_TIMEOUT_MS" in names_5000
    assert "PROCESS_TIMEOUT_MS" in names_5000
