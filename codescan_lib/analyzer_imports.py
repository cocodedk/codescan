"""Import tracking for CodeAnalyzer."""
import ast

from .bindings import ModuleScan, runtime_bound_names, scan_function
from .call_names import is_type_checking
from .constants import COLOR_IMPORTS
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
    blocked_names: set[str]  # names rebound in the scopes around the code being visited (see CallsMixin)
    module_rebound: set[str]
    origins: dict[str, str]  # where each imported name comes from (see call_names.import_origins)
    type_checking_depth: int = 0  # above 0 while inside the body of an `if TYPE_CHECKING:`

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            top = alias.name.split(".")[0]
            self._bind(alias.asname or top, alias.name if alias.asname else top, top, relative=False)
            self._record_import(alias.name, alias.asname or alias.name, None, alias.name)
        self._record_module_imports(node)
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
        self._record_module_imports(node)
        self.generic_visit(node)

    def visit_If(self, node: ast.If) -> None:
        self._walk_if(node, self)

    def _walk_if(self, node: ast.If, visitor: ast.NodeVisitor) -> None:
        """Visit an `if` with `visitor`; imports under `if TYPE_CHECKING:` never run, so they add no module import."""
        if not is_type_checking(node.test, self.origins, self.blocked_names):
            visitor.generic_visit(node)
            return
        visitor.visit(node.test)
        self.type_checking_depth += 1
        try:
            for statement in node.body:
                visitor.visit(statement)
        finally:
            self.type_checking_depth -= 1
        for statement in node.orelse:
            visitor.visit(statement)

    def record_skipped_imports(self, node: ast.AST) -> None:
        """A skipped function (a dunder method) leaves no Function node, but its imports still make module imports."""
        saved = self.blocked_names
        self.blocked_names = saved | set(scan_function(node).names)  # a parameter or local may shadow TYPE_CHECKING
        try:
            _SkippedImports(self).visit(node)
        finally:
            self.blocked_names = saved

    def record_exports(self, scan: ModuleScan, tree: ast.Module) -> None:
        """Queue what other modules can learn about this file's names: `exports` (see call_targets.exported_functions)
        and `bound`, every name the module binds (a package binding `x` shadows its submodule `x`)."""
        self.batch.add(
            LINKS, "UNWIND $rows AS row MATCH (f:File {path: $file}) SET f.exports = row.exports, f.bound = row.bound",
            exports=sorted(scan.clean_exports()), bound=sorted(runtime_bound_names(tree, self.origins, self.module_rebound)),
        )

    def _record_module_imports(self, node: ast.Import | ast.ImportFrom) -> None:
        """Queue each module this import reads on the File node (`line:module`, or `line:package:name` for a
        `from` import); finalize_graph() turns them into IMPORTS_MODULE edges once every file is known.

        Standard-library imports and imports under `if TYPE_CHECKING:` are skipped here.
        """
        if self.type_checking_depth:
            return
        if isinstance(node, ast.ImportFrom):
            package = self._absolute_module(node)
            if node.level == 0 and is_stdlib_module(package):
                return
            refs = [f"{package}:{alias.name}" for alias in node.names]
        else:
            refs = [alias.name for alias in node.names if not is_stdlib_module(alias.name)]
        for ref in refs:
            self.batch.add(
                LINKS, "UNWIND $rows AS row MATCH (f:File {path: $file}) "
                "SET f.import_refs = coalesce(f.import_refs, []) + row.ref",
                ref=f"{node.lineno}:{ref}",
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


class _SkippedImports(ast.NodeVisitor):
    """Finds the imports in a function the analyzer does not visit."""

    def __init__(self, owner: ImportsMixin) -> None:
        self.owner = owner

    def visit_Import(self, node: ast.Import | ast.ImportFrom) -> None:
        self.owner._record_module_imports(node)

    visit_ImportFrom = visit_Import

    def visit_If(self, node: ast.If) -> None:
        self.owner._walk_if(node, self)
