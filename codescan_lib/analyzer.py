import ast
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from .analyzer_calls import CallsMixin
from .analyzer_constants import ConstantsMixin
from .analyzer_imports import ImportsMixin
from .bindings import scan_module
from .call_names import deferred_nodes, import_origins, keeps_class
from .constants import COLOR_CLASS_CONTAINS
from .coverage_links import link_tests
from .forwarders import mark_forwarder
from .graph_batch import LINKS, NODES, GraphBatch
from .stats_collector import StatsCollector
from .utils import is_example_file, node_span


class CodeAnalyzer(CallsMixin, ConstantsMixin, ImportsMixin):
    def __init__(
        self,
        file_path: str,
        session: Any,
        is_test_file: bool = False,
        stats_collector: StatsCollector | None = None,
        skip_dunder_methods: bool = True,
        project_roots: set[str] | None = None,
    ):
        self.file_path: str = file_path
        self.session: Any = session
        self.current_class: str | None = None
        self.current_function: str | None = None
        self.current_function_line: int = -1  # tells apart same-named functions in one file
        self.is_test_file: bool = is_test_file
        self.is_example_file: bool = is_example_file(file_path)
        self.current_scope: str = "module"
        self.skip_dunder_methods: bool = skip_dunder_methods
        self.batch = GraphBatch(file_path)  # this file's writes, sent by flush()
        self.project_roots: set[str] = project_roots or set()  # top-level packages and modules of the scan
        self.external_names: set[str] = set()  # names this file imported from outside the project
        self.import_bindings: dict[str, str] = {}  # names this file imported from the project -> dotted name
        self.module_rebound: set[str] = set()  # see CallsMixin
        self.module_unstable: set[str] = set()
        self.scopes: list[tuple[set[str], set[str]]] = []
        self.origins: dict[str, str] = {}
        self.deferred: set[int] = set()
        self.class_outer_imports: list[tuple[set[str], dict[str, str]]] = []  # imports outside each open class
        self.blocked_names: set[str] = set()
        self.enclosing_bound: set[str] = set()
        self.sole_bindings: set[str] = set()
        self.instances: dict[str, tuple[str, int]] = {}

        # Use provided stats collector or create a new one
        self.stats: StatsCollector = (
            stats_collector if stats_collector is not None else StatsCollector()
        )

    @contextmanager
    def _scope(
        self, scope: str, cls: str | None, func: str | None, func_line: int,
        imports: tuple[set[str], dict[str, str]] | None = None,
    ) -> Iterator[None]:
        """Enter a class or function body, restoring the enclosing scope on exit.

        `imports` are the names the body starts with when it is not the current ones (a method does not
        see the imports of the class body it is written in).
        """
        saved = (self.current_scope, self.current_class, self.current_function, self.current_function_line)
        outer_imports = (self.external_names, self.import_bindings)
        start = imports or outer_imports
        self.external_names, self.import_bindings = set(start[0]), dict(start[1])
        self.current_scope, self.current_class = scope, cls
        self.current_function, self.current_function_line = func, func_line
        try:
            yield
        finally:
            self.external_names, self.import_bindings = outer_imports  # imports made inside stay inside
            (self.current_scope, self.current_class,
             self.current_function, self.current_function_line) = saved

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

    def visit_Module(self, node: ast.Module) -> None:
        scan = scan_module(node)
        self.module_rebound = scan.untrusted()
        self.blocked_names = set(self.module_rebound)  # module-level calls trust what a function would
        self.module_unstable, self.deferred, self.origins = scan.unstable(), deferred_nodes(node), import_origins(node)
        self.batch.add(  # which names another module can import with certainty (see call_targets.exported_functions)
            LINKS, "UNWIND $rows AS row MATCH (f:File {path: $file}) SET f.exports = row.exports",
            exports=sorted(scan.clean_exports()),
        )
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        line, end_line, length = node_span(node)
        self.stats.register_class(
            name=node.name,
            file_path=self.file_path,
            line=line,
            is_test=self.is_test_file,
            is_example=self.is_example_file,
        )
        self.batch.add(
            NODES,
            f"UNWIND $rows AS row MERGE (c{self._labels('Class')} "
            "{name: row.name, file: $file, line: row.line, end_line: row.end_line, length: row.length, "
            "nested: row.nested, plain: row.plain})",
            name=node.name, line=line, end_line=end_line, length=length, nested=self.current_scope != "module",
            plain=keeps_class(node.decorator_list, self.external_names - self.blocked_names, self.origins),
        )

        # Decorators and base classes run in the enclosing scope; the body in the class's
        self._visit_all([*node.decorator_list, *node.bases, *node.keywords])
        # A class body is invisible to its methods, and to the classes inside it: they see what is outside it
        outside = (
            self.class_outer_imports[-1] if self.current_scope == "class"
            else (set(self.external_names), dict(self.import_bindings))
        )
        with self._scope("class", node.name, self.current_function, self.current_function_line), \
                self._class_bindings(node):
            self.class_outer_imports.append(outside)
            try:
                self._visit_all(node.body)
            finally:
                self.class_outer_imports.pop()

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

        self.batch.add(
            NODES,
            f"""UNWIND $rows AS row
            MERGE (f{labels} {{name: row.name, file: $file, is_reference: false,
                               line: row.line, end_line: row.end_line, length: row.length,
                               parent_line: row.parent_line}})""",
            name=full_name, line=line, end_line=end_line, length=length, parent_line=self.current_function_line,
        )
        if owner:
            self.batch.add(
                LINKS,
                """UNWIND $rows AS row
                MATCH (c:Class {name: row.class_name, file: $file})
                MATCH (f:Function {name: row.func_name, file: $file, line: row.line, is_reference: false})
                MERGE (c)-[:CONTAINS {color: $color}]->(f)""",
                color=COLOR_CLASS_CONTAINS, class_name=owner, func_name=full_name, line=line,
            )

        mark_forwarder(self.batch, node, full_name, line, owner is not None, self.external_names)
        # Decorators, defaults and annotations run in the enclosing scope; the body in the function's
        self._visit_all([*node.decorator_list, node.args])
        if node.returns:
            self.visit(node.returns)
        outside = self.class_outer_imports[-1] if owner else None
        with self._scope("function", self.current_class, full_name, line, outside), self._bindings(node):
            self._visit_all(node.body)

    visit_AsyncFunctionDef = visit_FunctionDef

    def flush(self) -> None:
        """Write everything this file defines to the graph."""
        self.batch.flush(self.session)

    def process_test_relationships(self, custom_patterns: dict[str, Any] | None = None) -> None:
        """Relate test code to production code. Called at the end of analyze_file for test files."""
        if self.is_test_file:
            prefixes = (custom_patterns or {}).get("test_funcs")
            link_tests(self.session, prefixes)
