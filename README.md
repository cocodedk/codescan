# CodeScan: Python Static Code Analyzer with Neo4j Integration

## Website
- [English](https://cocodedk.github.io/codesacan/)
- [فارسی (Persian)](https://cocodedk.github.io/codesacan/fa/)

## Overview

`scanner.py` is a static code analysis tool designed to parse Python source code, extract structural and call-graph information, and store it in a Neo4j graph database. The tool is highly configurable via environment variables and is intended for advanced codebase exploration, dependency analysis, and visualization using Neo4j Browser with GraSS styling.

## Features
- **AST-based parsing**: Uses Python's `ast` module to traverse and analyze source code files.
- **Class and function extraction**: Identifies all classes, standalone functions, and class methods, including their file locations and line numbers.
- **Call graph construction**: Detects function calls, including argument names/values, and creates `CALLS` relationships in the graph.
- **Node labeling**: Assigns multiple labels to nodes for advanced visualization (e.g., `:Function`, `:MainFunction`, `:ClassFunction`, `:ReferenceFunction`).
- **Reference node handling**: Creates special nodes for called functions that are not defined in the scanned codebase.
- **Test detection and coverage**: Automatically identifies test components and establishes test coverage relationships:
  - Labels test files, functions, and classes with appropriate markers (`:Test`, `:TestFunction`, `:TestClass`)
  - Creates `TESTS` relationships between test code and the production code it tests
  - Configurable test patterns for different project structures and testing frameworks
- **Configurable directory traversal**: Skips specified directories (e.g., virtualenvs, `.git`, test folders) for efficient scanning.
- **Relative path storage**: Stores file paths relative to the project directory for improved portability.
- **Environment-based configuration**: Reads Neo4j connection and project settings from a `.env` file.
- **GraSS-compatible**: Designed for use with Neo4j Browser's GraSS stylesheet for custom node/relationship coloring.
- **Progress visualization**: Uses tqdm progress bars to show scanning progress and element discovery.
- **Statistics collection**: Gathers and displays detailed statistics about the scanned codebase.
- **Verbosity control**: Offers quiet and verbose modes for controlling output detail.

## Setting Up Your Environment

### Environment File Setup
CodeScan uses a `.env` file for configuration. Follow these steps to set it up:

1. Copy the example environment file to create your own:
   ```bash
   cp example.env .env
   ```

2. Edit the `.env` file and update the `PROJECT_DIR` variable to point to the path of the project you want to scan:
   ```
   PROJECT_DIR=/absolute/path/to/your/project/
   ```

   For example:
   - Linux/macOS: `PROJECT_DIR=/home/username/projects/my-python-project/`
   - Windows: `PROJECT_DIR=C:/Users/username/projects/my-python-project/`

3. Adjust other settings as needed:
   - Neo4j connection details (username, password, ports)
   - Logging options

### Alternative to Environment File
Instead of using the `.env` file, you can also specify the project directory directly when running the scanner:

```bash
python scanner.py --project-dir /path/to/your/project
```

## Architecture

### 1. AST Traversal
- The `CodeAnalyzer` class subclasses `ast.NodeVisitor`.
- Visits `ClassDef` and `FunctionDef` nodes to extract class/function metadata.
- Visits `Call` nodes to extract call relationships and argument information.

### 2. Node and Relationship Creation
- **File nodes**: Labeled `:File`, with additional labels for specific file types:
  - `:TestFile` for test files
  - `:ExampleFile` for example files
  - Properties include `path`, `type`, `is_test`, `is_example`
- **Class nodes**: Labeled `:Class`, properties include `name`, `file`, `line`, `end_line`.
- **Function nodes**: Labeled `:Function`, with additional labels:
  - `:MainFunction` for functions named `main`
  - `:ClassFunction` for methods inside classes
  - `:ReferenceFunction` for called-but-undefined functions
  - Properties: `name`, `file`, `line`, `end_line`, `is_reference`, `length`
- **Constant nodes**: Labeled `:Constant`, properties include `name`, `value`, `type`, `file`, `line`, `end_line`, `scope`
- **Relationships**:
  - `CONTAINS`: From `File` to `Class`, `Function`, or `Constant` (file contents)
  - `CONTAINS`: From `Class` to `Function` (class membership)
  - `CALLS`: From caller to callee, with properties `line` (call site), `args` (argument names/values)

### 3. Reference Node Handling
- If a function is called but not defined in the scanned codebase, a `:ReferenceFunction` node is created.
- When the function is later defined, all `CALLS` relationships to the reference node are redirected to the real function node.

### 4. Test Coverage Detection
- Test files, functions, and classes are automatically identified based on configurable patterns
- Test components receive appropriate labels (`:Test`, `:TestFunction`, `:TestClass`)
- `TESTS` relationships are created between test functions and production code through:
  - **Naming patterns**: A test function named `test_foo` likely tests the function `foo`
  - **Import analysis**: Test functions often import the modules/functions they test
  - **Call analysis**: Functions called by test functions are likely being tested
- All detection patterns are configurable for different project structures and frameworks

### 5. Configuration
- All connection and project settings are loaded from a `.env` file using `python-dotenv`.
- Example variables:
  - `NEO4J_USER`, `NEO4J_PASSWORD`, `NEO4J_HOST`, `NEO4J_PORT_BOLT`, `PROJECT_DIR`
- The ignore list for directories is hardcoded but can be extended.

### 6. Usage

#### Prerequisites
- Python 3.8+
- Neo4j 5.x (Docker recommended)
- Install dependencies:
  ```bash
  pip install -r requirements.txt
  ```

#### Running Neo4j
- Start Neo4j using Docker Compose:
  ```bash
  docker-compose up -d
  ```
- Neo4j Browser will be available at `http://localhost:7400` (or as configured).

#### Running the Scanner
- Ensure your `.env` file is configured (see "Setting Up Your Environment" section).
- Run the scanner:
  ```bash
  python scanner.py
  ```
- The script will:
  - Clear the Neo4j database
  - Traverse the project directory
  - Populate the graph with classes, functions, and call relationships

#### Output Control
Control the verbosity of scanner output:
```bash
# Minimal output (only errors)
python scanner.py --quiet

# Detailed output showing all elements found
python scanner.py --verbose
```

#### Visualizing in Neo4j Browser
- Use the provided `.grass` file for custom node/relationship coloring.
- Example queries:
  - `MATCH (n) RETURN n` (all nodes)
  - `MATCH (n)-[r]->(m) RETURN n, r, m` (all relationships)
  - `MATCH (f:Function) WHERE f.line > 100 RETURN f` (functions by line)
  - `MATCH ()-[r:CALLS {line: 42}]->() RETURN r` (calls at a specific line)
  - `MATCH (f:Function) RETURN f.name, f.file, f.length ORDER BY f.length DESC LIMIT 10` (find longest functions)
  - `MATCH (f:File)-[:CONTAINS]->(n) RETURN f.path, count(n) ORDER BY count(n) DESC LIMIT 10` (files with most elements)
  - `MATCH (f:File)-[:CONTAINS]->(n) WHERE n:Class OR n:Function RETURN f.path, labels(n), count(n) GROUP BY f.path, labels(n) ORDER BY f.path, labels(n)` (count of elements by type in each file)

## Advanced Details

- **Argument Extraction**: The scanner extracts argument names and constant values from function calls and stores them as a string in the `args` property of `CALLS` relationships.
- **Dunder Method Skipping**: Special methods (e.g., `__init__`, `__str__`) are ignored for clarity.
- **Built-in and stdlib call filtering**: Calls to Python built-ins and standard library modules are not included in the graph.
- **Error Handling**: Syntax errors and undecodable files are reported and skipped.
- **Extensibility**: The ignore list, node/relationship properties, and labeling logic can be easily extended for more advanced use cases.

## MCP Server and Cursor Integration

CodeScan includes an MCP (Model Context Protocol) server for advanced code graph querying and integration with tools like Cursor IDE.

### MCP Server (`codescan_mcp_server.py`)
This server exposes the code graph stored in Neo4j via the MCP protocol, making it accessible to compatible clients. It provides tools for listing files, functions, classes, call relationships, and unresolved references.

#### Available Tools
CodeScan provides various tools for code analysis through the MCP server:

- **Basic Code Structure**
  - `list_files` - List all files in the codebase with their types
  - `file_contents` - List all classes, functions, and constants in a specific file
  - `list_functions` - List functions in a specific file
  - `list_classes` - List classes in a specific file

- **Call Graph Analysis**
  - `callees` - Find functions called by a specific function
  - `callers` - Find functions that call a specific function
  - `transitive_calls` - Find paths between functions (whether one function eventually calls another)
  - `most_called_functions` - List functions with the most callers
  - `most_calling_functions` - List functions that call the most other functions

- **Test Coverage Analysis**
  - `untested_functions` - List functions without tests
  - `untested_classes` - List classes without tests
  - `test_coverage_ratio` - Get overall test coverage statistics
  - `functions_tested_by` - List functions tested by a specific test file
  - `tests_for_function` - List tests for a specific function

- **Miscellaneous Analysis**
  - `recursive_functions` - List functions that call themselves
  - `classes_with_no_methods` - List classes without any methods
  - `classes_with_most_methods` - List classes with the most methods
  - `function_call_arguments` - List arguments used in calls to a specific function
  - `repetitive_constants` - Find constants with identical values used in multiple places
  - `repetitive_constant_names` - Find constants with the same name but potentially different values used in multiple places

### Running the MCP Server
Use the provided shell script to launch the server (ensure your virtual environment is activated and Neo4j is running):

```bash
./run_mcp_stdio_server.sh
```

This will start the MCP server using stdio transport, ready for integration with Cursor or other MCP clients.

### Cursor IDE Integration
To use CodeScan's MCP server with Cursor IDE, add the following to your `.cursor/mcp.json` (adjust the path as needed):

```json
{
  "mcpServers": {
    "codescan_neo4j": {
      "command": "/path/to/codescan/run_mcp_stdio_server.sh",
      "args": []
    }
  }
}
```

After configuring, restart Cursor and open the MCP tools panel. You should see CodeScan's tools (e.g., `graph_summary`, `list_files`, `list_functions`, etc.) available for querying your codebase.

#### Troubleshooting
- Ensure Neo4j is running and accessible with the credentials in your `.env` file.
- Check the server logs for errors if tools do not appear in Cursor.
- The server must be started from the project root for relative paths to resolve correctly.

**Relevant files:**
- `codescan_mcp_server.py` — MCP server implementation
- `run_mcp_stdio_server.sh` — Shell script to launch the server

## Docker

```bash
docker pull ghcr.io/cocodedk/codesacan:latest
docker run ghcr.io/cocodedk/codesacan:latest
```

## Author

**Babak Bandpey** — [cocode.dk](https://cocode.dk) | [LinkedIn](https://linkedin.com/in/babakbandpey) | [GitHub](https://github.com/cocodedk)

## License

Apache-2.0 | © 2026 [Cocode](https://cocode.dk) | Created by [Babak Bandpey](https://linkedin.com/in/babakbandpey)
