import os
import sys
import tempfile
import shutil
import unittest

# Add parent directory to path to import scanner module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from codescan_lib.utils import is_test_file
from codescan_lib.constants import TEST_DIR_PATTERNS, TEST_FILE_PATTERNS

class TestTestDetection(unittest.TestCase):
    """Test the test file detection functionality."""

    def setUp(self):
        """Set up a temporary directory structure for testing."""
        self.temp_dir = tempfile.mkdtemp()

        # Create a standard test directory structure
        self.tests_dir = os.path.join(self.temp_dir, "tests")
        os.makedirs(self.tests_dir)

        # Create a module with its own tests directory
        self.module_dir = os.path.join(self.temp_dir, "module1")
        self.module_tests_dir = os.path.join(self.module_dir, "tests")
        os.makedirs(self.module_tests_dir)

        # Create various test files
        self.test_py_file = os.path.join(self.tests_dir, "test_example.py")
        self.py_test_file = os.path.join(self.tests_dir, "example_test.py")
        self.normal_file = os.path.join(self.temp_dir, "example.py")
        self.module_test_file = os.path.join(self.module_tests_dir, "test_module.py")

        # Create the files
        for file_path in [self.test_py_file, self.py_test_file, self.normal_file, self.module_test_file]:
            with open(file_path, "w") as f:
                f.write("# Test file\n")

    def tearDown(self):
        """Clean up the temporary directory."""
        shutil.rmtree(self.temp_dir)

    def test_test_directory_detection(self):
        """Test that files in test directories are detected."""
        # Files in the main tests directory
        self.assertTrue(is_test_file(self.test_py_file))
        self.assertTrue(is_test_file(self.py_test_file))

        # Files in nested test directories
        self.assertTrue(is_test_file(self.module_test_file))

    def test_test_filename_detection(self):
        """Test that files with test naming patterns are detected."""
        # Create test files outside of test directories
        test_file_outside = os.path.join(self.temp_dir, "test_outside.py")
        test_file_suffix = os.path.join(self.temp_dir, "outside_test.py")

        with open(test_file_outside, "w") as f:
            f.write("# Test file outside test directory\n")

        with open(test_file_suffix, "w") as f:
            f.write("# Test file with suffix outside test directory\n")

        # These should be detected based on filename patterns
        self.assertTrue(is_test_file(test_file_outside))
        self.assertTrue(is_test_file(test_file_suffix))

    def test_non_test_file_detection(self):
        """Test that non-test files are correctly identified."""
        self.assertFalse(is_test_file(self.normal_file))

    def test_example_file_detection(self):
        """Test that example files are not detected as test files."""
        # Create examples directory and files
        examples_dir = os.path.join(self.temp_dir, "examples")
        os.makedirs(examples_dir)

        # Different types of example files to test
        example_file = os.path.join(examples_dir, "example.py")
        example_test_file = os.path.join(examples_dir, "test_example.py")  # Test-like file in examples dir

        with open(example_file, "w") as f:
            f.write("# Example code\n")

        with open(example_test_file, "w") as f:
            f.write("# Example test code\n")

        # Make sure none of the examples are detected as test files
        self.assertFalse(is_test_file(example_file), "Example file was incorrectly detected as a test file")
        self.assertFalse(is_test_file(example_test_file), "Example test file was incorrectly detected as a test file")

    def test_custom_test_patterns(self):
        """Test with custom test directory and file patterns."""
        # Create a custom 'spec' directory
        spec_dir = os.path.join(self.temp_dir, "spec")
        os.makedirs(spec_dir)
        spec_file = os.path.join(spec_dir, "example_spec.py")

        with open(spec_file, "w") as f:
            f.write("# Spec file\n")

        # Temporarily override the test patterns
        original_dir_patterns = TEST_DIR_PATTERNS.copy()
        original_file_patterns = TEST_FILE_PATTERNS.copy()

        try:
            # Add 'spec' to the test directory patterns
            TEST_DIR_PATTERNS.append("spec")
            # Use absolute path when testing
            abs_spec_file = os.path.abspath(spec_file)

            # Print for debugging
            print(f"Testing path: {abs_spec_file}")
            print(f"Current TEST_DIR_PATTERNS: {TEST_DIR_PATTERNS}")

            # Force the normalized path to use forward slashes for consistent testing
            result = is_test_file(abs_spec_file.replace("\\", "/"))
            self.assertTrue(result, f"Expected {abs_spec_file} to be detected as a test file")

            # Test with only custom patterns (removing standard ones)
            TEST_DIR_PATTERNS.clear()
            TEST_DIR_PATTERNS.append("spec")
            TEST_FILE_PATTERNS.clear()
            TEST_FILE_PATTERNS.append("*_spec.py")

            # This should still be detected
            result = is_test_file(abs_spec_file.replace("\\", "/"))
            self.assertTrue(result)

        finally:
            # Restore original patterns
            TEST_DIR_PATTERNS.clear()
            TEST_DIR_PATTERNS.extend(original_dir_patterns)
            TEST_FILE_PATTERNS.clear()
            TEST_FILE_PATTERNS.extend(original_file_patterns)

    def test_relative_path_handling(self):
        """Test that relative paths are handled correctly."""
        # Convert to relative paths
        rel_test_file = os.path.relpath(self.test_py_file, os.getcwd())
        rel_normal_file = os.path.relpath(self.normal_file, os.getcwd())

        self.assertTrue(is_test_file(rel_test_file))
        self.assertFalse(is_test_file(rel_normal_file))


if __name__ == "__main__":
    unittest.main()
