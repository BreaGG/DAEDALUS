"""Graph algorithms over a case: Ariadne's thread (paths) and structural analysis.

Everything here is dependency-free and works on the plain entity/link lists stored
for a case, so it can be tested in isolation and reused from the API.
"""

from __future__ import annotations

import heapq
import random
from collections import defaultdict, deque
from itertools import combinations


class Graph:
    def __init__(self, nodes: list[str], links: list[dict]):
        self.nodes: list[str] = list(dict.fromkeys(nodes))
        known = set(self.nodes)
        self.out: dict[str, set[str]] = {n: set() for n in self.nodes}
        self.inc: dict[str, set[str]] = {n: set() for n in self.nodes}
        self.und: dict[str, set[str]] = {n: set() for n in self.nodes}
        self.weight: dict[frozenset, int] = defaultdict(int)
        self.labels: dict[tuple[str, str], list[str]] = defaultdict(list)
        for ln in links:
            a, b = ln["src"], ln["dst"]
            if a == b or a not in known or b not in known:
                continue
            self.out[a].add(b)
            self.inc[b].add(a)
            self.und[a].add(b)
            self.und[b].add(a)
            self.weight[frozenset((a, b))] += 1
            self.labels[(a, b)].append(ln.get("label") or "")

    @classmethod
    def from_case(cls, graph: dict) -> "Graph":
        return cls([e["id"] for e in graph["entities"]], graph["links"])

    def neighbors(self, n: str, directed: bool = False) -> set[str]:
        return self.out[n] if directed else self.und[n]

    def path_edges(self, path: list[str]) -> list[dict]:
        """The links that realise each hop of a path (direction as stored)."""
        hops = []
        for a, b in zip(path, path[1:]):
            if (a, b) in self.labels:
                hops.append({"src": a, "dst": b, "labels": self.labels[(a, b)], "forward": True})
            else:
                hops.append({"src": b, "dst": a, "labels": self.labels.get((b, a), []), "forward": False})
        return hops


# ------------------------------------------------------------------ Ariadne: paths
def shortest_path(g: Graph, src: str, dst: str, directed: bool = False,
                  banned_nodes: set[str] | None = None, banned_edges: set | None = None) -> list[str] | None:
    """Unweighted shortest path by BFS; None if unreachable."""
    if src not in g.out or dst not in g.out:
        return None
    if src == dst:
        return [src]
    banned_nodes = banned_nodes or set()
    banned_edges = banned_edges or set()
    prev: dict[str, str | None] = {src: None}
    q = deque([src])
    while q:
        v = q.popleft()
        for w in sorted(g.neighbors(v, directed)):
            if w in prev or w in banned_nodes:
                continue
            key = (v, w) if directed else frozenset((v, w))
            if key in banned_edges:
                continue
            prev[w] = v
            if w == dst:
                path = [w]
                while prev[path[-1]] is not None:
                    path.append(prev[path[-1]])
                return path[::-1]
            q.append(w)
    return None


def k_shortest_paths(g: Graph, src: str, dst: str, k: int = 5, max_len: int | None = None,
                     directed: bool = False) -> list[list[str]]:
    """Yen's algorithm: up to k loop-free paths, shortest first. max_len is in hops."""
    first = shortest_path(g, src, dst, directed)
    if not first or (max_len is not None and len(first) - 1 > max_len):
        return []
    found = [first]
    candidates: list[tuple[int, int, list[str]]] = []
    seen = {tuple(first)}
    counter = 0
    while len(found) < k:
        last = found[-1]
        for i in range(len(last) - 1):
            spur, root = last[i], last[: i + 1]
            banned_edges = set()
            for p in found:
                if len(p) > i + 1 and p[: i + 1] == root:
                    banned_edges.add((p[i], p[i + 1]) if directed else frozenset((p[i], p[i + 1])))
            spur_path = shortest_path(g, spur, dst, directed, set(root[:-1]), banned_edges)
            if not spur_path:
                continue
            total = root[:-1] + spur_path
            t = tuple(total)
            if t in seen or (max_len is not None and len(total) - 1 > max_len):
                continue
            seen.add(t)
            counter += 1
            heapq.heappush(candidates, (len(total), counter, total))
        if not candidates:
            break
        found.append(heapq.heappop(candidates)[2])
    return found


def connect(g: Graph, ids: list[str], directed: bool = False) -> dict:
    """Union of the shortest paths between every pair of the given entities."""
    ids = [i for i in dict.fromkeys(ids) if i in g.out][:25]
    nodes: set[str] = set(ids)
    edges: set[tuple[str, str]] = set()
    missing = []
    for a, b in combinations(ids, 2):
        p = shortest_path(g, a, b, directed)
        if not p:
            missing.append([a, b])
            continue
        nodes.update(p)
        for hop in g.path_edges(p):
            edges.add((hop["src"], hop["dst"]))
    return {"nodes": sorted(nodes), "edges": [list(e) for e in sorted(edges)], "unreachable": missing}


def ego(g: Graph, node: str, hops: int = 1) -> list[str]:
    """Entities within `hops` steps of a node (the node included)."""
    if node not in g.und:
        return []
    dist = {node: 0}
    q = deque([node])
    while q:
        v = q.popleft()
        if dist[v] >= hops:
            continue
        for w in g.und[v]:
            if w not in dist:
                dist[w] = dist[v] + 1
                q.append(w)
    return list(dist)


# ------------------------------------------------------------- structure analysis
def components(g: Graph) -> list[list[str]]:
    seen: set[str] = set()
    comps = []
    for n in g.nodes:
        if n in seen:
            continue
        comp, q = [], deque([n])
        seen.add(n)
        while q:
            v = q.popleft()
            comp.append(v)
            for w in g.und[v]:
                if w not in seen:
                    seen.add(w)
                    q.append(w)
        comps.append(comp)
    comps.sort(key=len, reverse=True)
    return comps


def betweenness(g: Graph, sample: int | None = None, seed: int = 7) -> dict[str, float]:
    """Brandes' betweenness on the undirected graph, normalised to [0, 1].

    For large graphs a random sample of source nodes approximates the result.
    """
    nodes = g.nodes
    n = len(nodes)
    cb = dict.fromkeys(nodes, 0.0)
    sources = nodes
    if sample and n > sample:
        sources = random.Random(seed).sample(nodes, sample)
    for s in sources:
        stack: list[str] = []
        preds: dict[str, list[str]] = {v: [] for v in nodes}
        sigma = dict.fromkeys(nodes, 0)
        sigma[s] = 1
        dist = dict.fromkeys(nodes, -1)
        dist[s] = 0
        q = deque([s])
        while q:
            v = q.popleft()
            stack.append(v)
            for w in g.und[v]:
                if dist[w] < 0:
                    dist[w] = dist[v] + 1
                    q.append(w)
                if dist[w] == dist[v] + 1:
                    sigma[w] += sigma[v]
                    preds[w].append(v)
        delta = dict.fromkeys(nodes, 0.0)
        while stack:
            w = stack.pop()
            for v in preds[w]:
                delta[v] += sigma[v] / sigma[w] * (1 + delta[w])
            if w != s:
                cb[w] += delta[w]
    scale = 1.0
    if sample and n > sample:
        scale = n / len(sources)
    norm = (n - 1) * (n - 2) if n > 2 else 1  # undirected: /2 for double counting, *2 for pair normalisation
    return {v: (c * scale) / norm for v, c in cb.items()}


def pagerank(g: Graph, damping: float = 0.85, iterations: int = 60, tol: float = 1e-9) -> dict[str, float]:
    n = len(g.nodes)
    if not n:
        return {}
    rank = dict.fromkeys(g.nodes, 1.0 / n)
    for _ in range(iterations):
        dangling = sum(rank[v] for v in g.nodes if not g.out[v])
        new = {}
        for v in g.nodes:
            s = sum(rank[u] / len(g.out[u]) for u in g.inc[v])
            new[v] = (1 - damping) / n + damping * (s + dangling / n)
        diff = sum(abs(new[v] - rank[v]) for v in g.nodes)
        rank = new
        if diff < tol:
            break
    return rank


def articulation_points(g: Graph) -> tuple[list[str], list[list[str]]]:
    """Choke points of the labyrinth: entities (and links) whose removal splits the graph."""
    disc: dict[str, int] = {}
    low: dict[str, int] = {}
    parent: dict[str, str | None] = {}
    aps: set[str] = set()
    bridges: list[list[str]] = []
    t = 0
    for root in g.nodes:
        if root in disc:
            continue
        disc[root] = low[root] = t
        t += 1
        parent[root] = None
        children = 0
        stack = [(root, iter(sorted(g.und[root])))]
        while stack:
            v, it = stack[-1]
            advanced = False
            for w in it:
                if w not in disc:
                    parent[w] = v
                    disc[w] = low[w] = t
                    t += 1
                    if v == root:
                        children += 1
                    stack.append((w, iter(sorted(g.und[w]))))
                    advanced = True
                    break
                if w != parent[v]:
                    low[v] = min(low[v], disc[w])
            if advanced:
                continue
            stack.pop()
            if stack:
                u = stack[-1][0]
                low[u] = min(low[u], low[v])
                if parent[u] is not None and low[v] >= disc[u]:
                    aps.add(u)
                if low[v] > disc[u]:
                    bridges.append([u, v])
        if children > 1:
            aps.add(root)
    return sorted(aps), bridges


def louvain(g: Graph, max_levels: int = 10) -> dict[str, int]:
    """Louvain community detection (modularity optimisation) on the undirected graph."""
    # weighted adjacency of the current level; nodes are ints after the first aggregation
    adj: dict = {n: {} for n in g.nodes}
    for key, w in g.weight.items():
        a, b = tuple(key)
        adj[a][b] = adj[a].get(b, 0) + w
        adj[b][a] = adj[b].get(a, 0) + w
    loops: dict = dict.fromkeys(g.nodes, 0.0)
    members: dict = {n: [n] for n in g.nodes}
    m = sum(g.weight.values())
    if m == 0:
        return {n: i for i, n in enumerate(g.nodes)}

    for _ in range(max_levels):
        nodes = sorted(adj, key=str)
        degree = {v: sum(adj[v].values()) + 2 * loops[v] for v in nodes}
        com = {v: v for v in nodes}
        tot = dict(degree)
        moved_any = False
        improved = True
        while improved:
            improved = False
            for v in nodes:
                c_old = com[v]
                tot[c_old] -= degree[v]
                links_to: dict = defaultdict(float)
                for w, wt in adj[v].items():
                    links_to[com[w]] += wt
                best, best_gain = c_old, links_to.get(c_old, 0.0) - tot[c_old] * degree[v] / (2 * m)
                for c, k_in in links_to.items():
                    gain = k_in - tot[c] * degree[v] / (2 * m)
                    if gain > best_gain + 1e-12:
                        best, best_gain = c, gain
                com[v] = best
                tot[best] += degree[v]
                if best != c_old:
                    improved = moved_any = True
        if not moved_any:
            break
        # aggregate communities into super-nodes
        groups: dict = defaultdict(list)
        for v in nodes:
            groups[com[v]].append(v)
        index = {c: i for i, c in enumerate(groups)}
        new_adj: dict = {i: {} for i in index.values()}
        new_loops: dict = dict.fromkeys(index.values(), 0.0)
        new_members: dict = {i: [] for i in index.values()}
        for v in nodes:
            cv = index[com[v]]
            new_members[cv].extend(members[v])
            new_loops[cv] += loops[v]
            for w, wt in adj[v].items():
                cw = index[com[w]]
                if cv == cw:
                    new_loops[cv] += wt / 2  # each internal edge is seen from both ends
                else:
                    new_adj[cv][cw] = new_adj[cv].get(cw, 0) + wt
        adj, loops, members = new_adj, new_loops, new_members

    # stable numbering: biggest community first
    ordered = sorted(members.values(), key=lambda ms: (-len(ms), str(sorted(ms, key=str)[0])))
    return {n: i for i, ms in enumerate(ordered) for n in ms}


def modularity(g: Graph, communities: dict[str, int]) -> float:
    m = sum(g.weight.values())
    if not m:
        return 0.0
    deg = {v: sum(g.weight[frozenset((v, w))] for w in g.und[v]) for v in g.nodes}
    internal: dict[int, float] = defaultdict(float)
    tot: dict[int, float] = defaultdict(float)
    for key, w in g.weight.items():
        a, b = tuple(key)
        if communities[a] == communities[b]:
            internal[communities[a]] += w
    for v in g.nodes:
        tot[communities[v]] += deg[v]
    return sum(internal[c] / m - (tot[c] / (2 * m)) ** 2 for c in tot)


def similar_pairs(g: Graph, types: dict[str, str], limit: int = 20, min_shared: int = 2,
                  hub_cap: int = 150) -> list[dict]:
    """Same-type entities sharing neighbours: candidates for being the same identity."""
    shared: dict[tuple[str, str], set[str]] = defaultdict(set)
    for mid in g.nodes:
        nbrs = sorted(g.und[mid])
        if len(nbrs) > hub_cap:
            continue
        for a, b in combinations(nbrs, 2):
            if types.get(a) == types.get(b):
                shared[(a, b)].add(mid)
    out = []
    for (a, b), mids in shared.items():
        if len(mids) < min_shared or b in g.und[a]:
            continue
        union = len(g.und[a] | g.und[b])
        out.append({"a": a, "b": b, "shared": sorted(mids), "jaccard": round(len(mids) / union, 3) if union else 0})
    out.sort(key=lambda x: (-len(x["shared"]), -x["jaccard"]))
    return out[:limit]


def similar_to(g: Graph, node: str, limit: int = 10) -> list[dict]:
    if node not in g.und:
        return []
    mine = g.und[node]
    scores = []
    candidates = {w for v in mine for w in g.und[v]} - {node}
    for c in candidates:
        inter = mine & g.und[c]
        if not inter:
            continue
        union = mine | g.und[c]
        scores.append({"id": c, "shared": sorted(inter), "jaccard": round(len(inter) / len(union), 3)})
    scores.sort(key=lambda x: (-x["jaccard"], -len(x["shared"])))
    return scores[:limit]


def analyze(graph: dict) -> dict:
    """Full structural report for a case graph."""
    g = Graph.from_case(graph)
    types = {e["id"]: e["type"] for e in graph["entities"]}
    n, m = len(g.nodes), sum(g.weight.values())
    comps = components(g)
    bc = betweenness(g, sample=300 if n > 1500 else None)
    pr = pagerank(g)
    deg = {v: len(g.und[v]) for v in g.nodes}
    comm = louvain(g)
    aps, bridges = articulation_points(g)
    top = sorted(g.nodes, key=lambda v: (-bc[v], -deg[v]))[:10]
    return {
        "stats": {
            "entities": n,
            "links": m,
            "components": len(comps),
            "largest_component": len(comps[0]) if comps else 0,
            "isolated": sum(1 for v in g.nodes if not g.und[v]),
            "density": round(2 * len(g.weight) / (n * (n - 1)), 4) if n > 1 else 0,
            "avg_degree": round(sum(deg.values()) / n, 2) if n else 0,
            "communities": len(set(comm.values())),
            "modularity": round(modularity(g, comm), 4),
        },
        "degree": deg,
        "betweenness": {k: round(v, 5) for k, v in bc.items()},
        "pagerank": {k: round(v, 5) for k, v in pr.items()},
        "communities": comm,
        "component": {v: i for i, comp in enumerate(comps) for v in comp},
        "articulation_points": aps,
        "bridges": bridges,
        "hubs": [{"id": v, "betweenness": round(bc[v], 4), "degree": deg[v]} for v in top if deg[v]],
        "similar": similar_pairs(g, types),
    }
