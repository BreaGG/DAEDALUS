from daedalus import graphalgo as ga


def graph(edges, extra_nodes=()):
    nodes = sorted({n for e in edges for n in e} | set(extra_nodes))
    return ga.Graph(nodes, [{"src": a, "dst": b, "label": f"{a}-{b}"} for a, b in edges])


def test_shortest_path_undirected_and_directed():
    g = graph([("a", "b"), ("b", "c"), ("d", "c")])
    assert ga.shortest_path(g, "a", "d") == ["a", "b", "c", "d"]
    # c -> d does not exist as a directed link
    assert ga.shortest_path(g, "a", "d", directed=True) is None
    assert ga.shortest_path(g, "a", "a") == ["a"]
    assert ga.shortest_path(g, "a", "zzz") is None


def test_k_shortest_paths_orders_by_length():
    g = graph([("a", "b"), ("b", "d"), ("a", "c"), ("c", "d"), ("a", "e"), ("e", "f"), ("f", "d")])
    paths = ga.k_shortest_paths(g, "a", "d", k=5)
    assert [len(p) - 1 for p in paths] == [2, 2, 3]
    assert {tuple(p) for p in paths} == {("a", "b", "d"), ("a", "c", "d"), ("a", "e", "f", "d")}
    assert len(ga.k_shortest_paths(g, "a", "d", k=5, max_len=2)) == 2


def test_path_edges_report_direction_and_labels():
    g = graph([("a", "b"), ("c", "b")])
    hops = g.path_edges(["a", "b", "c"])
    assert hops[0] == {"src": "a", "dst": "b", "labels": ["a-b"], "forward": True}
    assert hops[1]["forward"] is False and hops[1]["src"] == "c"


def test_articulation_points_and_bridges_barbell():
    g = graph([("a", "b"), ("b", "c"), ("c", "a"), ("c", "d"), ("d", "e"), ("e", "f"), ("f", "d")])
    aps, bridges = ga.articulation_points(g)
    assert aps == ["c", "d"]
    assert sorted(map(sorted, bridges)) == [["c", "d"]]


def test_betweenness_star():
    g = graph([("hub", x) for x in "abcd"])
    bc = ga.betweenness(g)
    assert round(bc["hub"], 6) == 1.0
    assert all(bc[x] == 0 for x in "abcd")


def test_louvain_finds_two_cliques():
    left = [(f"l{i}", f"l{j}") for i in range(5) for j in range(i + 1, 5)]
    right = [(f"r{i}", f"r{j}") for i in range(5) for j in range(i + 1, 5)]
    g = graph(left + right + [("l0", "r0")])
    comm = ga.louvain(g)
    assert len(set(comm.values())) == 2
    assert len({comm[f"l{i}"] for i in range(5)}) == 1
    assert comm["l1"] != comm["r1"]
    assert ga.modularity(g, comm) > 0.4


def test_connect_and_ego():
    g = graph([("a", "b"), ("b", "c"), ("c", "d"), ("x", "y")])
    r = ga.connect(g, ["a", "d", "x"])
    assert r["nodes"] == ["a", "b", "c", "d", "x"]
    assert len(r["edges"]) == 3
    assert len(r["unreachable"]) == 2
    assert sorted(ga.ego(g, "b", 1)) == ["a", "b", "c"]


def test_similar_pairs_and_similar_to():
    g = graph([("u1", "mail"), ("u2", "mail"), ("u1", "city"), ("u2", "city"), ("u1", "x")])
    types = {"u1": "username", "u2": "username", "mail": "email", "city": "location", "x": "url"}
    pairs = ga.similar_pairs(g, types)
    assert pairs[0]["a"] == "u1" and pairs[0]["b"] == "u2" and pairs[0]["shared"] == ["city", "mail"]
    assert ga.similar_to(g, "u2")[0]["id"] == "u1"


def test_analyze_handles_empty_and_small_graphs():
    empty = ga.analyze({"entities": [], "links": []})
    assert empty["stats"]["entities"] == 0
    rep = ga.analyze({"entities": [{"id": i, "type": "username"} for i in "abc"],
                      "links": [{"src": "a", "dst": "b", "label": ""}]})
    assert rep["stats"]["components"] == 2
    assert rep["stats"]["isolated"] == 1
    assert rep["hubs"][0]["id"] in ("a", "b")
