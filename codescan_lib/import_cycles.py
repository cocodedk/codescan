"""Find the cycles in a graph of file imports."""
from collections.abc import Iterable
from itertools import islice

MAX_CYCLE_LENGTH = 8  # longer loops are not searched: the search stays fast on a big import graph
MAX_STEPS = 2_000_000  # total work of one search; a graph that spends it all may list fewer cycles than exist

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


def _distances_to(rev: Graph, owner: dict[str, int], start: str, depth: int, budget: list[int]) -> dict[str, int]:
    """Steps from each node to `start` along imports, up to `depth`, through nodes of its group after it."""
    dist = {start: 0}
    frontier = [start]
    for step in range(1, depth + 1):
        following = []
        for node in frontier:
            for before in rev[node]:
                budget[0] -= 1
                if before not in dist and before > start and owner.get(before) == owner[start]:
                    dist[before] = step
                    following.append(before)
        frontier = following
    return dist


def _cycles_of_length(
    graph: Graph, rev: Graph, owner: dict[str, int], length: int, budget: list[int],
) -> Iterable[list[str]]:
    """Cycles of exactly `length` files, in path order, each starting at its smallest file.

    Only nodes that can still get back to the start in the steps left are followed, so the search does not
    wander. Every step taken spends from `budget`; the search ends when it is spent.
    """
    def extend(path: list[str], dist: dict[str, int]) -> Iterable[list[str]]:
        for nxt in graph[path[-1]]:
            if budget[0] <= 0:
                return
            budget[0] -= 1
            if nxt == path[0]:
                if len(path) == length:
                    yield list(path)
            elif nxt in dist and nxt not in path and len(path) + dist[nxt] <= length:
                yield from extend([*path, nxt], dist)

    for start in sorted(owner):
        if budget[0] <= 0:
            return
        yield from extend([start], _distances_to(rev, owner, start, length - 1, budget))


def find_cycles(edges: Iterable[tuple[str, str]], limit: int) -> list[list[str]]:
    """Up to `limit` distinct import cycles, shortest first, no longer than MAX_CYCLE_LENGTH files.

    A file importing itself is no cycle. Only the strongly connected groups are searched, one length at a
    time, and the search stops when `limit` cycles are found or MAX_STEPS steps are spent.
    """
    graph: Graph = {}
    for source, target in edges:
        if source != target:
            graph.setdefault(source, []).append(target)
            graph.setdefault(target, [])
    graph = {node: sorted(set(targets)) for node, targets in graph.items()}
    owner = {node: i for i, group in enumerate(strongly_connected(graph)) if len(group) > 1 for node in group}
    rev: Graph = {node: [] for node in graph}
    for source, targets in graph.items():
        for target in targets:
            rev[target].append(source)
    budget = [MAX_STEPS]
    found: list[list[str]] = []
    for length in range(2, MAX_CYCLE_LENGTH + 1):
        found.extend(islice(_cycles_of_length(graph, rev, owner, length, budget), limit - len(found)))
        if len(found) >= limit or budget[0] <= 0:
            break
    return found
