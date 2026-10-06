"""Graph pass that needs the whole project: which file each recorded import means."""
from typing import Any

from .call_targets import build_exporters
from .constants import COLOR_IMPORTS_MODULE
from .graph_batch import LINKS, GraphBatch

WRITE_IMPORTS = """UNWIND $rows AS row
    MATCH (a:File {path: row.source})
    MATCH (b:File {path: row.target})
    MERGE (a)-[r:IMPORTS_MODULE {line: row.line}]->(b)
    ON CREATE SET r.color = $color"""


def resolve_imports(session: Any) -> None:
    """Add `(:File)-[:IMPORTS_MODULE {line}]->(:File)` for each recorded import of a project module.

    A recorded name resolves to the longest dotted prefix that is a project module, so `pkg.sub.name` means
    `pkg/sub.py`, and a package means its `__init__.py` (build_exporters lets the package win over `pkg.py`).
    """
    rows = list(session.run("MATCH (f:File) RETURN f.path AS path, coalesce(f.import_refs, []) AS refs"))
    exporters = build_exporters([(row["path"], []) for row in rows])
    batch = GraphBatch("")
    for row in rows:
        for ref in row["refs"]:
            line, _, dotted = ref.partition(":")
            while dotted and dotted not in exporters:
                dotted = dotted.rpartition(".")[0]
            if dotted:
                batch.add(LINKS, WRITE_IMPORTS, COLOR_IMPORTS_MODULE,
                          source=row["path"], target=exporters[dotted][0], line=int(line))
    batch.flush(session)
