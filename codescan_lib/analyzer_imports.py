"""Import tracking for CodeAnalyzer."""
import ast

from .constants import COLOR_IMPORTS, TYPE_CHECKING_NAME
from .graph_batch import LINKS, GraphBatch
from .stats_collector import StatsCollector
from .utils import is_stdlib_module


class ImportsMixin(ast.NodeVisitor):
    """Visits imports: sorts imported names into outside code and project modules, and records test imports."""

    file_path: str
    batch: GraphBatch
    stats: StatsCollector
    is_test_file: bool
    current_function: str | None
    current_function_line: int
    external_names: set[str]  # names bound to the standard library or a third-party package
    import_bindings: dict[str, str]  # names bound to project code -> the dotted name they stand for
    project_roots: set[str]
    type_checking_depth: int = 0  # above 0 while inside the body of an `if TYPE_CHECKING:`

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            top = alias.name.split(".")[0]
            self._bind(alias.asname or top, alias.name if alias.asname else top, top, relative=False)
            self._record_import(alias.name, alias.asname or alias.name, None, alias.name)
            self._record_module_import(alias.name, node.lineno, relative=False)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = "." * node.level + (node.module or "")
        package = self._absolute_module(node)
        for alias in node.names:
            if alias.name != "*":
                top = (node.module or "").split(".")[0]
                self._bind(alias.asname or alias.name, f"{package}.{alias.name}".lstrip("."), top, node.level > 0)
            full_import = f"{module}.{alias.name}" if module else alias.name
            self._record_import(alias.name, alias.asname or alias.name, module or None, full_import)
            if alias.name != "*":
                self._record_module_import(f"{package}.{alias.name}".lstrip("."), node.lineno, node.level > 0)
        self.generic_visit(node)

    def visit_If(self, node: ast.If) -> None:
        """Imports under `if TYPE_CHECKING:` never run, so they add no module import."""
        if not _is_type_checking(node.test):
            self.generic_visit(node)
            return
        self.visit(node.test)
        self.type_checking_depth += 1
        try:
            for statement in node.body:
                self.visit(statement)
        finally:
            self.type_checking_depth -= 1
        for statement in node.orelse:
            self.visit(statement)

    def _record_module_import(self, dotted: str, line: int, relative: bool) -> None:
        """Queue `line: dotted` on the File node; finalize_graph() turns it into an IMPORTS_MODULE edge.

        Standard-library names are skipped here, the rest is matched to project files once every file is known.
        """
        if self.type_checking_depth or (not relative and is_stdlib_module(dotted)):
            return
        self.batch.add(
            LINKS, "UNWIND $rows AS row MATCH (f:File {path: $file}) "
            "SET f.import_refs = coalesce(f.import_refs, []) + row.ref",
            ref=f"{line}:{dotted}",
        )

    def _absolute_module(self, node: ast.ImportFrom) -> str:
        """Dotted name of the module a `from` import reads, relative imports resolved against this file."""
        if node.level == 0:
            return node.module or ""
        parts = self.file_path.replace("\\", "/").split("/")[:-1]
        parts = parts[: max(len(parts) - node.level + 1, 0)]
        return ".".join([*parts, *([node.module] if node.module else [])])

    def _bind(self, name: str, full_name: str, top: str, relative: bool) -> None:
        """Sort an imported name: standard-library and third-party names are skipped by calls."""
        if not relative and (is_stdlib_module(top) or top not in self.project_roots):
            self.external_names.add(name)
            self.import_bindings.pop(name, None)
        else:
            self.external_names.discard(name)
            self.import_bindings[name] = full_name

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


def _is_type_checking(test: ast.expr) -> bool:
    """`TYPE_CHECKING` or `typing.TYPE_CHECKING` (any module alias) as the whole condition."""
    return (isinstance(test, ast.Name) and test.id == TYPE_CHECKING_NAME) or (
        isinstance(test, ast.Attribute) and test.attr == TYPE_CHECKING_NAME)
