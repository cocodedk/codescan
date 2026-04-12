import ast
from typing import Any, Optional
from .constants import BUILTIN_FUNCTIONS, TEST_FUNCTION_PREFIXES
from .utils import is_stdlib_module, is_example_file
from .stats_collector import StatsCollector


class CodeAnalyzer(ast.NodeVisitor):
    def __init__(
        self,
        file_path: str,
        session: Any,
        is_test_file: bool = False,
        stats_collector: Optional[StatsCollector] = None,
        skip_dunder_methods: bool = True,
    ):
        self.file_path: str = file_path
        self.session: Any = session
        self.current_class: Optional[str] = None
        self.current_function: Optional[str] = None
        self.is_test_file: bool = is_test_file
        self.is_example_file: bool = is_example_file(file_path)
        self.current_scope: str = "module"
        self.skip_dunder_methods: bool = skip_dunder_methods

        # Use provided stats collector or create a new one
        self.stats: StatsCollector = (
            stats_collector if stats_collector is not None else StatsCollector()
        )

    def visit_ClassDef(self, node):
        class_name = node.name
        line_num = getattr(node, "lineno", -1)
        end_line_num = getattr(node, "end_lineno", -1)

        class_length = 0
        if line_num >= 0 and end_line_num >= 0:
            class_length = end_line_num - line_num + 1

        # Register class with stats collector
        self.stats.register_class(
            name=class_name,
            file_path=self.file_path,
            line=line_num,
            is_test=self.is_test_file,
            is_example=self.is_example_file,
        )

        self.current_class = class_name

        # Save previous scope and set current scope to class
        previous_scope = self.current_scope
        self.current_scope = "class"

        # Choose appropriate labels based on file type
        if self.is_test_file:
            self.session.run(
                "MERGE (c:Class:Test:TestClass {name: $name, file: $file, line: $line, end_line: $end_line, length: $length})",
                name=class_name,
                file=self.file_path,
                line=line_num,
                end_line=end_line_num,
                length=class_length,
            )
        elif self.is_example_file:
            self.session.run(
                "MERGE (c:Class:Example:ExampleClass {name: $name, file: $file, line: $line, end_line: $end_line, length: $length})",
                name=class_name,
                file=self.file_path,
                line=line_num,
                end_line=end_line_num,
                length=class_length,
            )
        else:
            self.session.run(
                "MERGE (c:Class {name: $name, file: $file, line: $line, end_line: $end_line, length: $length})",
                name=class_name,
                file=self.file_path,
                line=line_num,
                end_line=end_line_num,
                length=class_length,
            )

        self.generic_visit(node)
        self.current_class = None
        # Restore previous scope
        self.current_scope = previous_scope

    def visit_FunctionDef(self, node):
        function_name = node.name

        # Skip special methods and private methods if configured
        if (
            self.skip_dunder_methods
            and function_name.startswith("__")
            and function_name.endswith("__")
        ):
            self.stats.register_skipped_file(
                file_path=self.file_path,
                reason=f"Skipping dunder method: {function_name}",
            )
            return

        # Get line number information
        line_num = getattr(node, "lineno", -1)
        end_line_num = getattr(node, "end_lineno", -1)

        # Calculate function length (number of lines)
        function_length = 0
        if line_num >= 0 and end_line_num >= 0:
            function_length = (
                end_line_num - line_num + 1
            )  # +1 to include the function definition line

        full_name = (
            f"{self.current_class}.{function_name}"
            if self.current_class
            else function_name
        )
        self.current_function = full_name

        # Register function with stats collector
        self.stats.register_function(
            name=full_name,
            file_path=self.file_path,
            line=line_num,
            is_test=self.is_test_file,
            is_reference=False,
            length=function_length,
        )

        # Save previous scope and set current scope to function
        previous_scope = self.current_scope
        self.current_scope = "function"

        # Choose labels based on file type and other conditions
        if self.is_test_file:
            labels = ":Function:Test:TestFunction"
        elif self.is_example_file:
            labels = ":Function:Example:ExampleFunction"
        else:
            labels = ":Function"

        if function_name == "main":
            labels += ":MainFunction"
        if self.current_class:
            labels += ":ClassFunction"

        # Check if a reference node for this function already exists
        result = self.session.run(
            f"""
            MATCH (f{labels} {{name: $name, is_reference: true}})
            RETURN f
            """,
            name=function_name,
        ).data()

        # First create or update the function node
        self.session.run(
            f"""
            MERGE (f{labels} {{
                name: $name,
                file: $file,
                is_reference: false,
                line: $line,
                end_line: $end_line,
                length: $length
            }})
            """,
            name=full_name,
            file=self.file_path,
            line=line_num,
            end_line=end_line_num,
            length=function_length,
        )

        # If we previously created a reference node for this function by name only,
        # link any calls to the reference node to this defined function
        if result:
            self.session.run(
                """
                MATCH (ref:Function {name: $simple_name, is_reference: true})
                MATCH (defined:Function {name: $full_name, file: $file, is_reference: false})
                MATCH (caller)-[r:CALLS]->(ref)
                MERGE (caller)-[:CALLS {color: $edge_color}]->(defined)
                WITH ref, r
                DELETE r
                """,
                simple_name=function_name,
                full_name=full_name,
                file=self.file_path,
                edge_color="#FF9800",  # Orange for calls relationships
            )
        if self.current_class:
            self.session.run(
                """
                MATCH (c:Class {name: $class_name, file: $file})
                WITH c
                MATCH (f:Function {name: $func_name, file: $file})
                MERGE (c)-[:CONTAINS {color: $edge_color}]->(f)
                """,
                class_name=self.current_class,
                func_name=full_name,
                file=self.file_path,
                edge_color="#9C27B0",  # Purple for contains relationships
            )
        self.generic_visit(node)
        self.current_function = None
        # Restore previous scope
        self.current_scope = previous_scope

    def visit_Assign(self, node):
        """
        Visit assignment nodes to detect constant definitions.
        Constants are identified by all-uppercase names with underscores.
        """
        # Skip assignments in test files
        if self.is_test_file:
            self.generic_visit(node)
            return

        # Process each target in the assignment
        for target in node.targets:
            if isinstance(target, ast.Name):
                name = target.id
                # Check if name follows constant naming convention:
                # 1. All uppercase
                # 2. Contains at least one underscore
                # 3. Not just a single character
                if name.isupper() and "_" in name and len(name) > 1:
                    line_num = getattr(node, "lineno", -1)
                    end_line_num = getattr(node, "end_lineno", -1)

                    # Get the value and type of the constant
                    value, value_type = self._extract_constant_value(node.value)

                    # Register constant with stats collector
                    self.stats.register_constant(
                        name=name,
                        file_path=self.file_path,
                        line=line_num,
                        value=value,
                        type_name=value_type,
                    )

                    # Determine the container based on current scope
                    container_type = self.current_scope
                    container_name = None
                    if container_type == "class":
                        container_name = self.current_class
                    elif container_type == "function":
                        container_name = self.current_function

                    # Create the constant node
                    self._create_constant_node(
                        name,
                        value,
                        value_type,
                        line_num,
                        end_line_num,
                        container_type,
                        container_name,
                    )

        self.generic_visit(node)

    def _extract_constant_value(self, value_node):
        """
        Extract the value and type of a constant from its AST node.

        Args:
            value_node: The AST node representing the constant's value

        Returns:
            tuple: (string_value, type_name)
        """
        if value_node is None:
            return "None", "NoneType"

        if isinstance(value_node, ast.Constant):
            # Handle basic types (str, int, float, bool, None)
            python_value = value_node.value
            type_name = (
                type(python_value).__name__ if python_value is not None else "NoneType"
            )
            string_value = repr(python_value)
            return string_value, type_name

        elif isinstance(value_node, ast.List):
            # Handle lists
            return (
                f"[{', '.join(self._extract_constant_value(item)[0] for item in value_node.elts)}]",
                "list",
            )

        elif isinstance(value_node, ast.Dict):
            # Handle dictionaries
            keys = [
                self._extract_constant_value(k)[0] if k is not None else "None"
                for k in value_node.keys
            ]
            values = [
                self._extract_constant_value(v)[0] if v is not None else "None"
                for v in value_node.values
            ]
            items = [f"{k}: {v}" for k, v in zip(keys, values)]
            return f"{{{', '.join(items)}}}", "dict"

        elif isinstance(value_node, ast.Tuple):
            # Handle tuples
            return (
                f"({', '.join(self._extract_constant_value(item)[0] for item in value_node.elts)})",
                "tuple",
            )

        elif isinstance(value_node, ast.Set):
            # Handle sets
            return (
                f"{{{', '.join(self._extract_constant_value(item)[0] for item in value_node.elts)}}}",
                "set",
            )

        elif isinstance(value_node, ast.UnaryOp):
            # Handle unary operations like -1
            if isinstance(value_node.op, ast.USub):
                operand_value, operand_type = self._extract_constant_value(
                    value_node.operand
                )
                return f"-{operand_value}", operand_type
            else:
                return str(ast.dump(value_node)), "expression"

        else:
            # For other types or complex expressions, return a simplified representation
            return str(ast.dump(value_node)), "expression"

    def _create_constant_node(
        self,
        name,
        value,
        value_type,
        line_num,
        end_line_num,
        container_type,
        container_name=None,
    ):
        """
        Create a Constant node in the Neo4j database and link it to its container.

        Args:
            name: Name of the constant
            value: String representation of the constant's value
            value_type: Type of the constant (str, int, float, etc.)
            line_num: Line number where the constant is defined
            end_line_num: End line number for multi-line constants
            container_type: Type of container (module, class, function)
            container_name: Name of the container (if applicable)
        """
        # Create the constant node
        self.session.run(
            """
            MERGE (c:Constant {
                name: $name,
                value: $value,
                type: $type,
                file: $file,
                line: $line,
                end_line: $end_line,
                scope: $scope
            })
            RETURN c
            """,
            name=name,
            value=value,
            type=value_type,
            file=self.file_path,
            line=line_num,
            end_line=end_line_num,
            scope=container_type,
        ).single()

        # Create relationship to container
        if container_type == "module":
            # For module-level constants, there's no specific container node
            # We could create a File node if needed, but for now we just leave it
            pass
        elif container_type == "class" and container_name:
            # Link to class
            self.session.run(
                """
                MATCH (constant:Constant {name: $constant_name, file: $file, line: $line})
                MATCH (class:Class {name: $class_name, file: $file})
                MERGE (class)-[:DEFINES {color: $edge_color}]->(constant)
                """,
                constant_name=name,
                class_name=container_name,
                file=self.file_path,
                line=line_num,
                edge_color="#E91E63",  # Pink for defines relationships
            )
        elif container_type == "function" and container_name:
            # Link to function
            self.session.run(
                """
                MATCH (constant:Constant {name: $constant_name, file: $file, line: $line})
                MATCH (function:Function {name: $function_name, file: $file})
                MERGE (function)-[:DEFINES {color: $edge_color}]->(constant)
                """,
                constant_name=name,
                function_name=container_name,
                file=self.file_path,
                line=line_num,
                edge_color="#E91E63",  # Pink for defines relationships
            )

    def visit_Call(self, node):
        module_name = None
        # Get line number information for the call
        line_num = getattr(node, "lineno", -1)

        # Extract both function name and module if available
        if isinstance(node.func, ast.Name):
            called_func = node.func.id
        elif isinstance(node.func, ast.Attribute):
            called_func = node.func.attr
            if isinstance(node.func.value, ast.Name):
                module_name = node.func.value.id
        else:
            called_func = None

        # Extract argument names or values
        arg_names = []
        for arg in node.args:
            if isinstance(arg, ast.Name):
                arg_names.append(arg.id)
            elif isinstance(arg, ast.Constant):
                arg_names.append(repr(arg.value))
            else:
                arg_names.append(ast.dump(arg))
        args_str = ", ".join(arg_names)

        # Skip built-in functions and standard library calls
        if called_func in BUILTIN_FUNCTIONS:
            return

        if module_name and is_stdlib_module(module_name):
            return

        # Register call with stats collector
        if called_func and self.current_function:
            self.stats.register_call(
                caller=self.current_function,
                callee=called_func,
                file_path=self.file_path,
                line=line_num,
                args=args_str,
            )

        if called_func and self.current_function:
            # First check if this function already exists
            result = self.session.run(
                """
                MATCH (f:Function {name: $name})
                RETURN f.file AS file
                """,
                name=called_func,
            ).data()

            # If the function has been defined in a file we know about, use that
            if result and result[0]["file"] is not None:
                # Use the first file we found that defined this function
                known_file = result[0]["file"]
                self.session.run(
                    """
                    MATCH (called:Function {name: $called_name, file: $known_file})
                    WITH called
                    MATCH (caller:Function {name: $caller_name, file: $caller_file})
                    MERGE (caller)-[:CALLS {color: $edge_color, line: $line, args: $args}]->(called)
                    """,
                    called_name=called_func,
                    known_file=known_file,
                    caller_name=self.current_function,
                    caller_file=self.file_path,
                    edge_color="#FF9800",  # Orange for calls relationships
                    line=line_num,
                    args=args_str,
                )
            else:
                # Function not yet defined anywhere we've seen, create a reference node
                self.session.run(
                    """
                    MERGE (called:Function:ReferenceFunction {name: $called_name, is_reference: true, file: $file, line: $line, end_line: $end_line, length: 0})
                    WITH called
                    MATCH (caller:Function {name: $caller_name, file: $file})
                    MERGE (caller)-[:CALLS {line: $line, args: $args}]->(called)
                    """,
                    called_name=called_func,
                    caller_name=self.current_function,
                    file=self.file_path,
                    line=line_num,
                    end_line=-1,
                    args=args_str,
                )

                # Register reference function with stats collector
                self.stats.register_function(
                    name=called_func,
                    file_path=self.file_path,
                    line=line_num,
                    is_reference=True,
                )

        self.generic_visit(node)

    def visit_Import(self, node):
        """
        Process Import nodes and track imports in test files.
        """
        for alias in node.names:
            imported_name = alias.name
            alias_name = alias.asname or imported_name

            if self.is_test_file:
                # Register import with stats collector
                self.stats.register_import(
                    name=imported_name, file_path=self.file_path, is_test=True
                )

                # Track imports for later analysis of test relationships
                self.session.run(
                    """
                    MERGE (i:Import {name: $name, alias: $alias, file: $file})
                    WITH i
                    MATCH (f:Function {name: $func_name, file: $file})
                    MERGE (f)-[:IMPORTS {color: $edge_color}]->(i)
                """,
                    name=imported_name,
                    alias=alias_name,
                    file=self.file_path,
                    func_name=self.current_function,
                    edge_color="#4CAF50",
                )  # Green for imports

        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        """
        Process ImportFrom nodes and track imports in test files.
        """
        module = node.module
        for alias in node.names:
            imported_name = alias.name
            alias_name = alias.asname or imported_name
            full_import = f"{module}.{imported_name}" if module else imported_name

            if self.is_test_file:
                # Register import with stats collector
                self.stats.register_import(
                    name=full_import, file_path=self.file_path, is_test=True
                )

                # Track imports for later analysis of test relationships
                self.session.run(
                    """
                    MERGE (i:Import {name: $name, module: $module, alias: $alias, file: $file})
                    WITH i
                    MATCH (f:Function {name: $func_name, file: $file})
                    MERGE (f)-[:IMPORTS {color: $edge_color}]->(i)
                """,
                    name=imported_name,
                    module=module,
                    alias=alias_name,
                    file=self.file_path,
                    func_name=self.current_function,
                    edge_color="#4CAF50",
                )

        self.generic_visit(node)

    def process_test_relationships(self, custom_patterns=None):
        """
        Process relationships between test code and production code.
        Called at the end of analyze_file for test files.

        Args:
            custom_patterns: Dictionary with custom test patterns
        """
        if not self.is_test_file:
            return

        # Use custom patterns if provided, otherwise use defaults from constants
        function_prefixes = (
            custom_patterns["test_funcs"]
            if custom_patterns and "test_funcs" in custom_patterns
            else TEST_FUNCTION_PREFIXES
        )

        # Process based on configurable naming patterns
        for prefix in function_prefixes:
            prefix_len = len(prefix)
            self.session.run(
                """
                MATCH (test:TestFunction)
                WHERE test.name STARTS WITH $prefix
                WITH test, substring(test.name, $prefix_len) AS tested_name
                MATCH (prod:Function)
                WHERE NOT prod:TestFunction AND prod.name = tested_name
                MERGE (test)-[:TESTS {method: 'naming_pattern', color: $edge_color}]->(prod)
            """,
                prefix=prefix,
                prefix_len=prefix_len,
                edge_color="#3F51B5",
            )  # Indigo for tests

        # Process based on imports
        self.session.run(
            """
            MATCH (test:TestFunction)-[:IMPORTS]->(i:Import)
            MATCH (prod:Function)
            WHERE NOT prod:TestFunction AND prod.name = i.name
            MERGE (test)-[:TESTS {method: 'import', color: $edge_color}]->(prod)
        """,
            edge_color="#3F51B5",
        )

        # Process based on calls
        self.session.run(
            """
            MATCH (test:TestFunction)-[:CALLS]->(prod:Function)
            WHERE NOT prod:TestFunction
            MERGE (test)-[:TESTS {method: 'call', color: $edge_color}]->(prod)
        """,
            edge_color="#3F51B5",
        )
