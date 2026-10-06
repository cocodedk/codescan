"""Collect one file's graph writes and send each kind in one UNWIND query.

Nodes are written before links, so a link's MATCH always finds the class,
function or constant it connects, whatever order the visitor met them in.
"""
from typing import Any

NODES, LINKS = 0, 1


class GraphBatch:
    """Queued rows of one file's graph writes, sent together by flush()."""

    def __init__(self, file_path: str) -> None:
        self.file_path = file_path
        self._rows: dict[tuple[int, str], list[dict[str, Any]]] = {}
        self._colors: dict[tuple[int, str], str | None] = {}

    def add(self, tier: int, query: str, color: str | None = None, **row: Any) -> None:
        """Queue one row for `query`, an `UNWIND $rows AS row` statement."""
        key = (tier, query)
        self._rows.setdefault(key, []).append(row)
        self._colors[key] = color

    def flush(self, session: Any) -> None:
        """Write every queued row, nodes first, one query per kind."""
        for key in sorted(self._rows, key=lambda k: k[0]):
            session.run(key[1], rows=self._rows[key], file=self.file_path, color=self._colors[key])
        self._rows.clear()
        self._colors.clear()
