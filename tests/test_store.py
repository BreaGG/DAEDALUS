from daedalus.store import Store, merge_props


def test_merge_props():
    out = merge_props({"a": [1, 2], "b": {"x": 1}, "c": "old"}, {"a": [2, 3], "b": {"y": 2}, "c": "new", "d": ""})
    assert out == {"a": [1, 2, 3], "b": {"x": 1, "y": 2}, "c": "new"}


def test_upsert_merges_and_keeps_root(tmp_path):
    s = Store(tmp_path / "db.sqlite")
    c = s.create_case("x")
    e1, created = s.upsert_entity(c["id"], "email", "A@B.com", {"_sources": ["one"]}, root=True)
    assert created and e1["value"] == "a@b.com" and e1["root"]
    e2, created = s.upsert_entity(c["id"], "email", "a@b.com", {"_sources": ["two"], "k": 1})
    assert not created and e2["root"] and e2["props"]["_sources"] == ["one", "two"] and e2["props"]["k"] == 1


def test_delete_cascades_and_merge_repoints(tmp_path):
    s = Store(tmp_path / "db.sqlite")
    cid = s.create_case("x")["id"]
    a, _ = s.upsert_entity(cid, "username", "alpha")
    b, _ = s.upsert_entity(cid, "username", "alpha2", {"bio": "dup"})
    m, _ = s.upsert_entity(cid, "email", "m@x.com")
    s.add_link(cid, b["id"], m["id"], "uses")
    s.update_entity(cid, b["id"], notes="note b")
    merged = s.merge_entities(cid, a["id"], [b["id"]])
    assert merged["props"]["bio"] == "dup" and merged["props"]["_aliases"] == ["alpha2"]
    assert "note b" in merged["notes"]
    assert s.links(cid) == [{"src": a["id"], "dst": m["id"], "label": "uses", "transform": ""}]
    assert s.get_entity(cid, b["id"]) is None
    s.delete_entities(cid, [m["id"]])
    assert s.links(cid) == []


def test_update_entity_replace_and_bookmark(tmp_path):
    s = Store(tmp_path / "db.sqlite")
    cid = s.create_case("x")["id"]
    e, _ = s.upsert_entity(cid, "domain", "example.com", {"a": 1, "b": 2})
    e = s.update_entity(cid, e["id"], replace={"a": None, "c": 3}, bookmark="red")
    assert e["props"] == {"b": 2, "c": 3} and e["bookmark"] == "red"
    e = s.update_entity(cid, e["id"], bookmark="not-a-colour")
    assert e["bookmark"] == ""


def test_case_lifecycle(tmp_path):
    s = Store(tmp_path / "db.sqlite")
    c = s.create_case("  ")
    assert c["name"] == "Untitled"
    s.update_case(c["id"], name="Renamed", layout={"positions": {"x": [1, 2]}})
    assert s.get_case(c["id"])["layout"]["positions"]["x"] == [1, 2]
    s.upsert_entity(c["id"], "ip", "1.1.1.1")
    assert s.list_cases()[0]["entities"] == 1
    s.delete_case(c["id"])
    assert s.get_case(c["id"]) is None and s.entities(c["id"]) == []
