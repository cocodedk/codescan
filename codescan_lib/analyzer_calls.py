"""Call recording for CodeAnalyzer."""
import ast

from .call_names import call_kind, callee_name, dotted_name, receiver_hints
from .graph_batch import LINKS, GraphBatch
from .stats_collector import StatsCollector


class CallsMixin(ast.NodeVisitor):
    """Visits calls, and the assignments that tell which class a local name holds."""

    file_path: str
    batch: GraphBatch
    stats: StatsCollector
    current_function: str | None
    current_function_line: int
    external_names: set[str]
    import_bindings: dict[str, str]
    instances: dict[tuple[str | None, int], dict[str, str]]  # per function: local name -> class it was built from

    def visit_Assign(self, node: ast.Assign) -> None:
        super().visit_Assign(node)  # type: ignore[misc]  # reads the value, then the targets
        self._bind_instances(node.targets, node.value)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        super().visit_AnnAssign(node)  # type: ignore[misc]
        if node.value is not None:
            self._bind_instances([node.target], node.value)

    def visit_Name(self, node: ast.Name) -> None:
        """Any other way of binding a name (unpacking, `+=`, `for`, `with`, `:=`, `del`) forgets its class."""
        if self.current_function and not isinstance(node.ctx, ast.Load):
            self._local_instances().pop(node.id, None)

    def _local_instances(self) -> dict[str, str]:
        return self.instances.setdefault((self.current_function, self.current_function_line), {})

    def _bind_instances(self, targets: list[ast.expr], value: ast.expr) -> None:
        """Remember `x = Foo()` for the current function, with Foo read through the file's imports."""
        if not self.current_function or not isinstance(value, ast.Call):
            return
        if callee_name(value.func, self.external_names) is None:
            return
        built = dotted_name(value.func, self.import_bindings)
        for target in targets:
            if built and isinstance(target, ast.Name):
                self._local_instances()[target.id] = built

    def visit_Call(self, node: ast.Call) -> None:
        callee = callee_name(node.func, self.external_names)
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
            recv_class, recv_module = receiver_hints(node.func, self.import_bindings, self._local_instances())
            # One placeholder per callee name; resolve_calls() re-points the edge at the real definition
            self.batch.add(
                LINKS,
                """UNWIND $rows AS row
                MERGE (called:Function:ReferenceFunction {name: row.called_name, is_reference: true})
                ON CREATE SET called.file = $file, called.line = row.line, called.end_line = -1, called.length = 0
                WITH called, row
                MATCH (caller:Function {name: row.caller_name, file: $file, line: row.caller_line, is_reference: false})
                MERGE (caller)-[:CALLS {line: row.line, args: row.args, kind: row.kind,
                                      recv_class: row.recv_class, recv_module: row.recv_module}]->(called)""",
                called_name=callee, caller_name=self.current_function,
                caller_line=self.current_function_line, line=line, args=args, kind=call_kind(node.func),
                recv_class=recv_class, recv_module=recv_module,
            )

        # Calls nested in the arguments (or the callee expression) still count
        self.generic_visit(node)
