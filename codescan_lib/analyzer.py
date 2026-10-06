import ast
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from .analyzer_constants import ConstantsMixin
from .analyzer_imports import ImportsMixin
from .constants import BUILTIN_FUNCTIONS, COLOR_CLASS_CONTAINS
from .relationships import link_tests
from .stats_collector import StatsCollector
from .utils import is_example_file, node_span


class CodeAnalyzer(ConstantsMixin, ImportsMixin):
    def __init__(
        self,
        file_path: str,
        session: Any,
        is_test_file: bool = False,
        stats_collector: StatsCollector | None = None,
        skip_dunder_methods: bool = True,
    ):
        self.file_path: str = file_path
        self.session: Any = session
        self.current_class: str | None = None
        self.current_function: str | None = None
        self.is_test_file: bool = is_test_file
        self.is_example_file: bool = is_example_file(file_path)
        self.current_scope: str = "module"
        self.skip_dunder_methods: bool = skip_dunder_methods
        self.stdlib_names: set[str] = set()  # names this file imported from the standard library

        # Use provided stats collector or create a new one
        self.stats: StatsCollector = (
            stats_collector if stats_collector is not None else StatsCollector()
        )

    @contextmanager
    def _scope(self, scope: str, cls: str | None, func: str | None) -> Iterator[None]:
        """Enter a class or function body, restoring the enclosing scope on exit."""
        saved = (self.current_scope, self.current_class, self.current_function)
        self.current_scope, self.current_class, self.current_function = scope, cls, func
        try:
            yield
        finally:
            self.current_scope, self.current_class, self.current_function = saved

    def _labels(self, kind: str) -> str:
        """Neo4j labels for a Class or Function node, by the kind of file it lives in."""
        if self.is_test_file:
            return f":{kind}:Test:Test{kind}"
        if self.is_example_file:
            return f":{kind}:Example:Example{kind}"
        return f":{kind}"

    def _visit_all(self, nodes: list[Any]) -> None:
        for child in nodes:
            self.visit(child)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        line, end_line, length = node_span(node)
        self.stats.register_class(
            name=node.name,
            file_path=self.file_path,
            line=line,
            is_test=self.is_test_file,
            is_example=self.is_example_file,
        )
        self.session.run(
            f"MERGE (c{self._labels('Class')} {{name: $name, file: $file, line: $line, end_line: $end_line, length: $length}})",
            name=node.name,
            file=self.file_path,
            line=line,
            end_line=end_line,
            length=length,
        )

        # Decorators and base classes run in the enclosing scope; the body in the class's
        self._visit_all([*node.decorator_list, *node.bases, *node.keywords])
        with self._scope("class", node.name, self.current_function):
            self._visit_all(node.body)

    def visit_FunctionDef(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        name = node.name
        if self.skip_dunder_methods and name.startswith("__") and name.endswith("__"):
            return

        line, end_line, length = node_span(node)
        owner = self.current_class if self.current_scope == "class" else None
        full_name = f"{owner}.{name}" if owner else name

        self.stats.register_function(
            name=full_name,
            file_path=self.file_path,
            line=line,
            is_test=self.is_test_file,
            is_reference=False,
            length=length,
        )

        labels = self._labels("Function")
        if name == "main":
            labels += ":MainFunction"
        if owner:
            labels += ":ClassFunction"

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
            line=line,
            end_line=end_line,
            length=length,
        )
        if owner:
            self.session.run(
                """
                MATCH (c:Class {name: $class_name, file: $file})
                WITH c
                MATCH (f:Function {name: $func_name, file: $file})
                MERGE (c)-[:CONTAINS {color: $edge_color}]->(f)
                """,
                class_name=owner,
                func_name=full_name,
                file=self.file_path,
                edge_color=COLOR_CLASS_CONTAINS,
            )

        # Decorators, defaults and annotations run in the enclosing scope; the body in the function's
        self._visit_all([*node.decorator_list, node.args])
        if node.returns:
            self.visit(node.returns)
        with self._scope("function", self.current_class, full_name):
            self._visit_all(node.body)

    visit_AsyncFunctionDef = visit_FunctionDef

    def _callee_name(self, func: ast.expr) -> str | None:
        """Name of the called function, or None for builtins and standard-library calls."""
        if isinstance(func, ast.Name):
            skipped = func.id in BUILTIN_FUNCTIONS or func.id in self.stdlib_names
            return None if skipped else func.id
        if isinstance(func, ast.Attribute):
            root = func.value
            while isinstance(root, ast.Attribute):
                root = root.value
            if isinstance(root, ast.Name) and root.id in self.stdlib_names:
                return None
            return func.attr
        return None

    def visit_Call(self, node: ast.Call) -> None:
        callee = self._callee_name(node.func)
        if callee and self.current_function:
            line = getattr(node, "lineno", -1)
            args = ", ".join(ast.unparse(arg) for arg in node.args)
            self.stats.register_call(
                caller=self.current_function,
                callee=callee,
                file_path=self.file_path,
                line=line,
                args=args,
            )
            # One placeholder per callee name; resolve_calls() re-points the edge at the real definition
            self.session.run(
                """
                MERGE (called:Function:ReferenceFunction {name: $called_name, is_reference: true})
                ON CREATE SET called.file = $file, called.line = $line, called.end_line = -1, called.length = 0
                WITH called
                MATCH (caller:Function {name: $caller_name, file: $file})
                MERGE (caller)-[:CALLS {line: $line, args: $args, bare: $bare}]->(called)
                """,
                called_name=callee,
                caller_name=self.current_function,
                file=self.file_path,
                line=line,
                args=args,
                bare=isinstance(node.func, ast.Name),
            )
            self.stats.register_function(
                name=callee, file_path=self.file_path, line=line, is_reference=True
            )

        # Calls nested in the arguments (or the callee expression) still count
        self.generic_visit(node)

    def process_test_relationships(self, custom_patterns: dict[str, Any] | None = None) -> None:
        """Relate test code to production code. Called at the end of analyze_file for test files."""
        if self.is_test_file:
            prefixes = (custom_patterns or {}).get("test_funcs")
            link_tests(self.session, prefixes)
