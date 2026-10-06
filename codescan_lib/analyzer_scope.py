"""Scope tracking for CodeAnalyzer."""
import ast
from collections.abc import Iterator
from contextlib import contextmanager


class ScopeMixin(ast.NodeVisitor):
    """Tracks the class or function body being visited, and the imports it sees."""

    current_scope: str
    current_class: str | None
    current_function: str | None
    current_function_line: int
    external_names: set[str]
    import_bindings: dict[str, str]

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
