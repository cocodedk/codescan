"""Constant detection for CodeAnalyzer."""
import ast

from .constant_values import extract_constant_value
from .constants import COLOR_DEFINES
from .graph_batch import LINKS, NODES, GraphBatch
from .stats_collector import StatsCollector
from .utils import node_span


def is_constant_name(name: str) -> bool:
    """Constants are upper-case names with at least one underscore."""
    return name.isupper() and "_" in name and len(name) > 1


class ConstantsMixin(ast.NodeVisitor):
    """Visits assignments and stores upper-case names as Constant nodes."""

    file_path: str
    batch: GraphBatch
    stats: StatsCollector
    is_test_file: bool
    current_scope: str
    current_class: str | None
    current_function: str | None
    current_function_line: int

    def visit_Assign(self, node: ast.Assign) -> None:
        self._record_constants(node, node.targets, node.value)
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if node.value is not None:
            self._record_constants(node, [node.target], node.value)
        self.generic_visit(node)

    def _record_constants(self, node: ast.stmt, targets: list[ast.expr], value: ast.expr) -> None:
        """Store upper-case assignment targets as Constant nodes (never in test files)."""
        if self.is_test_file:
            return
        line, end_line, _ = node_span(node)
        for target in targets:
            if not (isinstance(target, ast.Name) and is_constant_name(target.id)):
                continue
            text, type_name = extract_constant_value(value)
            self.stats.register_constant(
                name=target.id, file_path=self.file_path, line=line, value=text, type_name=type_name
            )
            container = (
                self.current_class if self.current_scope == "class"
                else self.current_function if self.current_scope == "function"
                else None
            )
            self._create_constant_node(target.id, text, type_name, line, end_line, container)

    def _create_constant_node(
        self,
        name: str,
        value: str,
        value_type: str,
        line_num: int,
        end_line_num: int,
        container_name: str | None,
    ) -> None:
        """Create a Constant node and link it to the class or function that defines it."""
        self.batch.add(
            NODES,
            """UNWIND $rows AS row
            MERGE (c:Constant {name: row.name, value: row.value, type: row.type, file: $file,
                               line: row.line, end_line: row.end_line, scope: row.scope})""",
            name=name, value=value, type=value_type, line=line_num, end_line=end_line_num,
            scope=self.current_scope,
        )
        if self.current_scope == "module" or not container_name:
            return
        owner_label = "Class" if self.current_scope == "class" else "Function"
        owner_extra = ", line: row.owner_line, is_reference: false" if owner_label == "Function" else ""
        self.batch.add(
            LINKS,
            f"""UNWIND $rows AS row
            MATCH (constant:Constant {{name: row.constant_name, file: $file, line: row.line}})
            MATCH (owner:{owner_label} {{name: row.owner_name, file: $file{owner_extra}}})
            MERGE (owner)-[:DEFINES {{color: $color}}]->(constant)""",
            color=COLOR_DEFINES, constant_name=name, owner_name=container_name,
            owner_line=self.current_function_line, line=line_num,
        )
