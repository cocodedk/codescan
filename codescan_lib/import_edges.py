"""Graph pass that needs the whole project: which file each recorded import means."""
from typing import Any

from .call_targets import Exporters, build_exporters
from .constants import COLOR_IMPORTS_MODULE
from .graph_batch import LINKS, GraphBatch

SRC_DIR = "src"  # a src layout: `src/pkg/a.py` is imported as `pkg.a`

WRITE_IMPORTS = """UNWIND $rows AS row
    MATCH (a:File {path: row.source})
    MATCH (b:File {path: row.target})
    MERGE (a)-[r:IMPORTS_MODULE {line: row.line}]->(b)
    ON CREATE SET r.color = $color"""


def module_index(files: list[tuple[str, list[str]]]) -> Exporters:
    """Module name -> (file, names that module binds). A module under `src/` is also known without `src.`.

    A top-level module of the same name wins over the one under `src/`.
    """
    exporters = build_exporters(files)
    for module, entry in list(exporters.items()):
        if module.startswith(f"{SRC_DIR}."):
            exporters.setdefault(module[len(SRC_DIR) + 1:], entry)
    return exporters


def resolve_ref(ref: str, modules: Exporters) -> str:
    """The project file a recorded import means, or "" when it is outside the project.

    `module` resolves to the longest dotted prefix that is a project module. `package:name` (`from package
    import name`) means the package itself when it binds `name`, else its submodule `name`, else the longest
    prefix of the package.
    """
    _, *parts = ref.split(":")
    dotted = parts[0]
    if len(parts) == 2:
        name = parts[1]
        file, bound = modules.get(dotted, ("", set()))
        if name in bound:
            return file
        dotted = f"{dotted}.{name}".lstrip(".") if f"{dotted}.{name}".lstrip(".") in modules else dotted
    while dotted and dotted not in modules:
        dotted = dotted.rpartition(".")[0]
    return modules[dotted][0] if dotted else ""


def resolve_imports(session: Any) -> None:
    """Add `(:File)-[:IMPORTS_MODULE {line}]->(:File)` for each recorded import of a project module.

    The edges are rebuilt from the recorded imports each time, so none outlives a change in what a module means.
    """
    rows = list(session.run(
        "MATCH (f:File) RETURN f.path AS path, coalesce(f.import_refs, []) AS refs, coalesce(f.bound, []) AS bound"))
    modules = module_index([(row["path"], row["bound"]) for row in rows])
    session.run("MATCH ()-[r:IMPORTS_MODULE]->() DELETE r")
    batch = GraphBatch("")
    for row in rows:
        for ref in row["refs"]:
            target = resolve_ref(ref, modules)
            if target:
                batch.add(LINKS, WRITE_IMPORTS, COLOR_IMPORTS_MODULE,
                          source=row["path"], target=target, line=int(ref.partition(":")[0]))
    batch.flush(session)
