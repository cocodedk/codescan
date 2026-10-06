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


def resolve_ref(ref: str, modules: Exporters, source: str) -> str:
    """The project file a recorded import means, or "" when it is outside the project or is `source` itself.

    `module` resolves to the longest dotted prefix that is a project module. `package:name` (`from package
    import name`) means the package when it binds `name` (and is not `source`: a package never imports itself),
    else its submodule `name`, else the longest prefix of the package. `package:*` means the package.
    """
    _, *parts = ref.split(":")
    dotted = parts[0]
    if len(parts) == 2 and parts[1] != "*":
        file, bound = modules.get(dotted, ("", set()))
        if parts[1] in bound and file != source:
            return file
        submodule = f"{dotted}.{parts[1]}".lstrip(".")
        dotted = submodule if submodule in modules else dotted
    while dotted and dotted not in modules:
        dotted = dotted.rpartition(".")[0]
    target = modules[dotted][0] if dotted else ""
    return "" if target == source else target


def with_star_names(rows: list[Any]) -> Exporters:
    """Module index where each file also binds the names the modules it star-imports bind (one level deep)."""
    own = module_index([(row["path"], row["bound"]) for row in rows])
    names = {file: set(bound) for file, bound in own.values()}
    bound = {row["path"]: set(row["bound"]) for row in rows}
    for row in rows:
        for ref in row["refs"]:
            if ref.endswith(":*"):
                bound[row["path"]] |= names.get(resolve_ref(ref, own, row["path"]), set())
    return module_index([(path, list(names)) for path, names in bound.items()])


def resolve_imports(session: Any) -> None:
    """Add `(:File)-[:IMPORTS_MODULE {line}]->(:File)` for each recorded import of a project module.

    The edges are rebuilt from the recorded imports each time, so none outlives a change in what a module means.
    """
    rows = list(session.run(
        "MATCH (f:File) RETURN f.path AS path, coalesce(f.import_refs, []) AS refs, coalesce(f.bound, []) AS bound"))
    modules = with_star_names(rows)
    session.run("MATCH ()-[r:IMPORTS_MODULE]->() DELETE r")
    batch = GraphBatch("")
    for row in rows:
        for ref in row["refs"]:
            target = resolve_ref(ref, modules, row["path"])
            if target:
                batch.add(LINKS, WRITE_IMPORTS, COLOR_IMPORTS_MODULE,
                          source=row["path"], target=target, line=int(ref.partition(":")[0]))
    batch.flush(session)
