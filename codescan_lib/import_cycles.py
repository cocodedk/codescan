"""Find the cycles in a graph of file imports."""
from collections.abc import Iterable

MAX_CYCLE_LENGTH = 8  # longer loops are not searched: the search stays fast on a big import graph

Graph = dict[str, list[str]]


def strongly_connected(graph: Graph) -> list[set[str]]:
    """The groups of nodes that can all reach each other (Tarjan, without recursion)."""
    index: dict[str, int] = {}
    low: dict[str, int] = {}
    stack: list[str] = []
    on_stack: set[str] = set()
    groups: list[set[str]] = []
    for root in graph:
        if root in index:
            continue
        index[root] = low[root] = len(index)
        stack.append(root)
        on_stack.add(root)
        work = [(root, iter(graph[root]))]
        while work:
            node, successors = work[-1]
            for nxt in successors:
                if nxt not in index:
                    index[nxt] = low[nxt] = len(index)
                    stack.append(nxt)
                    on_stack.add(nxt)
                    work.append((nxt, iter(graph[nxt])))
                    break
                if nxt in on_stack:
                    low[node] = min(low[node], index[nxt])
            else:
                work.pop()
                if work:
                    low[work[-1][0]] = min(low[work[-1][0]], low[node])
                if low[node] == index[node]:
                    group = set()
                    while node not in group:
                        member = stack.pop()
                        on_stack.discard(member)
                        group.add(member)
                    groups.append(group)
    return groups


def _cycles_of_length(graph: Graph, group: set[str], length: int) -> Iterable[list[str]]:
    """Every cycle of exactly `length` files inside `group`, each starting at its smallest file."""
    def extend(path: list[str]) -> Iterable[list[str]]:
        for nxt in graph[path[-1]]:
            if nxt == path[0] and len(path) == length:
                yield list(path)
            elif nxt > path[0] and nxt in group and nxt not in path and len(path) < length:
                yield from extend([*path, nxt])

    for start in sorted(group):
        yield from extend([start])


def find_cycles(edges: Iterable[tuple[str, str]], limit: int) -> list[list[str]]:
    """Up to `limit` distinct import cycles, shortest first, no longer than MAX_CYCLE_LENGTH files.

    A file importing itself is no cycle. Only the strongly connected groups are searched.
    """
    graph: Graph = {}
    for source, target in edges:
        if source != target:
            graph.setdefault(source, []).append(target)
            graph.setdefault(target, [])
    graph = {node: sorted(set(targets)) for node, targets in graph.items()}
    groups = [group for group in strongly_connected(graph) if len(group) > 1]
    found: list[list[str]] = []
    for length in range(2, MAX_CYCLE_LENGTH + 1):
        for group in groups:
            found.extend(_cycles_of_length(graph, group, length))
        found.sort(key=lambda c: (len(c), c))
        if len(found) >= limit:
            break
    return found[:limit]
