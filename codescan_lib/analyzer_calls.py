"""Call recording for CodeAnalyzer."""
import ast
from collections.abc import Iterator
from contextlib import contextmanager

from .bindings import scan_function
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
    current_scope: str
    module_rebound: set[str]  # names the module binds more than once: never trusted as a receiver or an import
    blocked_names: set[str]  # names this call's function, or one around it, rebinds: never trusted as a receiver
    enclosing_bound: set[str]  # every name the functions around the one being visited bind, imports included
    sole_bindings: set[str]  # names this function binds exactly once, by something other than an import
    instances: dict[str, tuple[str, int]]  # this function: local name -> (class it was built from, line)

    @contextmanager
    def _bindings(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> Iterator[None]:
        """Trust only receivers this function (and the ones around it) cannot have rebound.

        Inside, a function around this one is never trusted for any name it binds, imports included.
        This function is trusted for a name it imports only once and that nothing outside imported too.
        """
        scan = scan_function(node)
        saved = (self.blocked_names, self.enclosing_bound, self.sole_bindings, self.instances)
        imported_outside = {*self.import_bindings, *self.external_names}
        rebound = {
            *scan.names,
            *(name for name, count in scan.imports.items() if count > 1),
            *(scan.imports.keys() & imported_outside),
        }
        self.blocked_names = self.enclosing_bound | rebound | self.module_rebound
        self.enclosing_bound = self.enclosing_bound | scan.names.keys() | scan.imports.keys()
        self.sole_bindings = {name for name, count in scan.names.items() if count == 1 and name not in scan.imports}
        self.instances = {}
        try:
            yield
        finally:
            self.blocked_names, self.enclosing_bound, self.sole_bindings, self.instances = saved

    def visit_Assign(self, node: ast.Assign) -> None:
        """Remember `x = Foo()` when it is the function's only binding of `x` (and `x` is a function local)."""
        super().visit_Assign(node)  # type: ignore[misc]
        value = node.value
        if self.current_scope != "function" or not isinstance(value, ast.Call):
            return
        if callee_name(value.func, self.external_names) is None:
            return
        built = dotted_name(value.func, self.import_bindings, self.blocked_names)
        for target in node.targets:
            if built and isinstance(target, ast.Name) and target.id in self.sole_bindings:
                self.instances[target.id] = (built, node.end_lineno or node.lineno)

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
            recv_class, recv_module = receiver_hints(
                node.func, self.import_bindings, self.instances, self.blocked_names, line
            )
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
