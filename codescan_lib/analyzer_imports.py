"""Import tracking for CodeAnalyzer."""
import ast

from .constants import COLOR_IMPORTS
from .graph_batch import LINKS, GraphBatch
from .stats_collector import StatsCollector
from .utils import is_stdlib_module


class ImportsMixin(ast.NodeVisitor):
    """Visits imports: remembers standard-library names and records imports made by tests."""

    file_path: str
    batch: GraphBatch
    stats: StatsCollector
    is_test_file: bool
    current_function: str | None
    current_function_line: int
    stdlib_names: set[str]

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            if is_stdlib_module(alias.name):
                self.stdlib_names.add(alias.asname or alias.name.split(".")[0])
            self._record_import(alias.name, alias.asname or alias.name, None, alias.name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = "." * node.level + (node.module or "")
        for alias in node.names:
            if node.level == 0 and node.module and is_stdlib_module(node.module):
                self.stdlib_names.add(alias.asname or alias.name)
            full_import = f"{module}.{alias.name}" if module else alias.name
            self._record_import(alias.name, alias.asname or alias.name, module or None, full_import)
        self.generic_visit(node)

    def _record_import(self, name: str, alias: str, module: str | None, full_name: str) -> None:
        """Track an import in a test file, to relate the test to the code it imports."""
        if not self.is_test_file:
            return
        self.stats.register_import(name=full_name, file_path=self.file_path, is_test=True)
        module_prop = ", module: row.module" if module else ""
        self.batch.add(
            LINKS,
            f"""UNWIND $rows AS row
            MERGE (i:Import {{name: row.name{module_prop}, alias: row.alias, file: $file}})
            WITH i, row
            MATCH (f:Function {{name: row.func_name, file: $file, line: row.func_line, is_reference: false}})
            MERGE (f)-[:IMPORTS {{color: $color}}]->(i)""",
            color=COLOR_IMPORTS, name=name, module=module, alias=alias,
            func_name=self.current_function, func_line=self.current_function_line,
        )
