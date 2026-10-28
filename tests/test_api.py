import json

import pytest
from fastapi.testclient import TestClient

from daedalus.api import create_app


@pytest.fixture
def client(tmp_path, router):
    router.add(r"internetdb\.shodan\.io/203\.0\.113\.9", json_body={
        "ports": [443], "hostnames": ["edge.example.com"], "vulns": ["CVE-2021-44228"], "cpes": [], "tags": []})
    app = create_app(tmp_path, transport=router.transport, password="")
    with TestClient(app) as c:
        yield c


def new_case(client, name="Case"):
    return client.post("/api/cases", json={"name": name}).json()["id"]


def add(client, cid, value, **kw):
    r = client.post(f"/api/cases/{cid}/entities", json={"value": value, **kw})
    assert r.status_code == 200, r.text
    return r.json()


def test_meta_and_index(client):
    meta = client.get("/api/meta").json()
    assert "username" in meta["entity_types"] and len(meta["transforms"]) > 40
    assert {m["name"] for m in meta["machines"]} >= {"domain_footprint", "labyrinth"}
    page = client.get("/")
    assert page.status_code == 200 and "DAEDALUS" in page.text and "__VERSION__" not in page.text
    assert client.get("/js/main.js").status_code == 200


def test_entities_links_and_paths(client):
    cid = new_case(client)
    a = add(client, cid, "teolabrys")["entity"]
    assert a["type"] == "username" and a["root"]
    e = add(client, cid, "teo@example.com", parent=a["id"], label="uses")
    assert e["link"] == {"src": a["id"], "dst": "email:teo@example.com", "label": "uses", "transform": "manual"}
    assert not e["entity"]["root"]
    d = add(client, cid, "example.com", parent=e["entity"]["id"])["entity"]
    r = client.post(f"/api/cases/{cid}/paths", json={"src": a["id"], "dst": d["id"]}).json()
    assert r["paths"][0]["nodes"] == [a["id"], "email:teo@example.com", d["id"]]
    assert r["paths"][0]["hops"][0]["labels"] == ["uses"]
    # direction matters when asked
    r = client.post(f"/api/cases/{cid}/paths", json={"src": d["id"], "dst": a["id"], "directed": True}).json()
    assert r["paths"] == []
    conn = client.post(f"/api/cases/{cid}/connect", json={"ids": [a["id"], d["id"]]}).json()
    assert len(conn["nodes"]) == 3
    an = client.get(f"/api/cases/{cid}/analysis").json()
    assert an["stats"]["entities"] == 3 and an["articulation_points"] == ["email:teo@example.com"]
    # manual link + delete
    assert client.post(f"/api/cases/{cid}/links", json={"src": a["id"], "dst": d["id"], "label": "owns"}).status_code == 200
    assert client.post(f"/api/cases/{cid}/links", json={"src": a["id"], "dst": a["id"]}).status_code == 400
    assert client.post(f"/api/cases/{cid}/links/delete", json={"src": a["id"], "dst": d["id"], "label": "owns"}).json()["ok"]


def test_update_rename_merge_delete(client):
    cid = new_case(client)
    a = add(client, cid, "alpha")["entity"]
    b = add(client, cid, "b@example.com", parent=a["id"])["entity"]
    r = client.post(f"/api/cases/{cid}/entities/update", json={"id": a["id"], "props": {"x": 1}, "notes": "hi",
                                                                 "bookmark": "green"}).json()
    assert r["entity"]["props"]["x"] == 1 and r["entity"]["notes"] == "hi" and r["entity"]["bookmark"] == "green"
    r = client.post(f"/api/cases/{cid}/entities/update", json={"id": a["id"], "value": "Alpha2"}).json()
    assert r["renamed_from"] == a["id"] and r["entity"]["id"] == "username:alpha2"
    assert r["links"][0]["src"] == "username:alpha2"
    c = add(client, cid, "alpha3")["entity"]
    m = client.post(f"/api/cases/{cid}/entities/merge", json={"keep": "username:alpha2", "drop": [c["id"]]}).json()
    assert "alpha3" in m["entity"]["props"]["_aliases"]
    d = client.post(f"/api/cases/{cid}/entities/delete", json={"ids": [b["id"]]}).json()
    assert d["deleted"] == 1
    graph = client.get(f"/api/cases/{cid}").json()
    assert graph["links"] == [] and len(graph["entities"]) == 1


def test_validation_errors(client):
    cid = new_case(client)
    assert client.post(f"/api/cases/{cid}/entities", json={"value": "  "}).status_code == 400
    assert client.post(f"/api/cases/{cid}/entities", json={"value": "x", "type": "nope"}).status_code == 400
    assert client.get("/api/cases/999").status_code == 404
    assert client.post(f"/api/cases/{cid}/run", json={"entity_ids": [], "transforms": ["nope"]}).status_code == 400
    assert client.post(f"/api/cases/{cid}/machine", json={"entity_ids": [], "machine": "nope"}).status_code == 400


def test_export_import_roundtrip(client):
    cid = new_case(client, "Round <trip> & co")
    a = add(client, cid, "teolabrys")["entity"]
    add(client, cid, "teo@example.com", parent=a["id"], label="uses")
    client.patch(f"/api/cases/{cid}", json={"notes": "n", "layout": {"positions": {a["id"]: [1, 2]}}})
    exp = client.get(f"/api/cases/{cid}/export?format=json")
    assert exp.status_code == 200 and "attachment" in exp.headers["content-disposition"]
    data = exp.json()
    assert len(data["entities"]) == 2 and data["links"][0]["label"] == "uses"
    gml = client.get(f"/api/cases/{cid}/export?format=graphml").text
    assert "<graphml" in gml and "Round_trip" in gml and 'source="username:teolabrys"' in gml
    csv_text = client.get(f"/api/cases/{cid}/export?format=csv").text
    assert csv_text.splitlines()[0].startswith("id,type,value")
    links_csv = client.get(f"/api/cases/{cid}/export?format=links-csv").text
    assert "username:teolabrys,email:teo@example.com,uses" in links_csv
    imp = client.post("/api/import", files={"file": ("x.json", json.dumps(data), "application/json")}).json()
    g = client.get(f"/api/cases/{imp['id']}").json()
    assert len(g["entities"]) == 2 and len(g["links"]) == 1
    assert g["case"]["layout"]["positions"][a["id"]] == [1, 2] and g["case"]["notes"] == "n"
    assert client.post("/api/import", files={"file": ("x.json", "nope", "application/json")}).status_code == 400


def test_settings_mask_keys(client):
    s = client.put("/api/settings", json={"api_keys": {"shodan": "ABCDEFGHIJKL", "bogus": "x"}, "result_limit": "12"}).json()
    assert s["api_keys"]["shodan"] == {"label": "Shodan", "url": "https://account.shodan.io/", "set": True,
                                       "masked": "ABC…JKL"}
    assert "bogus" not in s["api_keys"] and s["result_limit"] == 12
    meta = client.get("/api/meta").json()
    assert next(t for t in meta["transforms"] if t["name"] == "shodan_host")["ready"] is True
    s = client.put("/api/settings", json={"api_keys": {"shodan": ""}}).json()
    assert s["api_keys"]["shodan"]["set"] is False


def test_run_transform_streams_events(client):
    cid = new_case(client)
    ip = add(client, cid, "203.0.113.9")["entity"]
    job = client.post(f"/api/cases/{cid}/run", json={"entity_ids": [ip["id"]], "transforms": ["shodan_internetdb"]}).json()
    events = []
    with client.stream("GET", f"/api/jobs/{job['job_id']}/events") as r:
        for line in r.iter_lines():
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))
                if events[-1]["type"] in ("done", "error"):
                    break
    kinds = [e["type"] for e in events]
    assert kinds[0] == "plan" and kinds[-1] == "done" and "run" in kinds
    created = {e["entity"]["id"] for e in events if e["type"] == "entity" and e["created"]}
    assert created == {"hostname:edge.example.com", "vulnerability:CVE-2021-44228"}
    assert all(e["parent"] == ip["id"] for e in events if e["type"] == "entity" and e["created"])
    runs = client.get(f"/api/cases/{cid}/runs?entity={ip['id']}").json()
    assert runs[-1]["status"] == "ok" and runs[-1]["found"] == 2


def test_upload_image_exif(client, tmp_path):
    from PIL import Image

    img = Image.new("RGB", (8, 8), "red")
    exif = img.getexif()
    exif[0x013B] = "Jane Roe"
    exif[0x0110] = "Pixel 7"
    gps = {1: "N", 2: (40.0, 25.0, 0.0), 3: "W", 4: (3.0, 42.0, 0.0)}
    exif[0x8825] = gps
    path = tmp_path / "p.jpg"
    img.save(path, exif=exif)
    cid = new_case(client)
    r = client.post(f"/api/cases/{cid}/upload", files={"file": ("p.jpg", path.read_bytes(), "image/jpeg")})
    assert r.status_code == 200, r.text
    g = client.get(f"/api/cases/{cid}").json()
    types = sorted(e["type"] for e in g["entities"])
    assert types == ["hash", "image", "location", "person"]
    loc = next(e for e in g["entities"] if e["type"] == "location")
    assert loc["props"]["_lat"] == pytest.approx(40.416667, abs=1e-4) and loc["props"]["_lon"] == pytest.approx(-3.7, abs=1e-4)
    assert client.post(f"/api/cases/{cid}/upload", files={"file": ("x.jpg", b"nope", "image/jpeg")}).status_code == 400


def test_password_protection(tmp_path, router):
    app = create_app(tmp_path, transport=router.transport, password="s3cret")
    with TestClient(app) as c:
        assert c.get("/api/meta").status_code == 401
        assert c.get("/api/meta", auth=("anyone", "wrong")).status_code == 401
        assert c.get("/api/meta", auth=("anyone", "s3cret")).status_code == 200
        assert c.get("/", auth=("daedalus", "s3cret")).status_code == 200


def test_language_setting_defaults_to_english(client, tmp_path):
    meta = client.get("/api/meta").json()
    assert list(meta["languages"]) == ["en", "es"]
    assert client.get("/api/settings").json()["lang"] == "en"
    assert client.put("/api/settings", json={"lang": "fr"}).json()["lang"] == "en"  # unknown languages ignored
    assert client.put("/api/settings", json={"lang": "es"}).json()["lang"] == "es"
    assert json.loads((tmp_path / "settings.json").read_text())["lang"] == "es"
    client.put("/api/settings", json={"lang": "en"})
    # defaults are not written, so a future default change still reaches existing installs
    assert "lang" not in json.loads((tmp_path / "settings.json").read_text())


def test_typed_coordinates_land_on_the_map(client):
    cid = new_case(client)
    r = client.post(f"/api/cases/{cid}/entities", json={"value": "39.4699, -0.3763"}).json()
    assert r["entity"]["type"] == "location"
    assert r["entity"]["props"]["_lat"] == 39.4699 and r["entity"]["props"]["_lon"] == -0.3763
    named = client.post(f"/api/cases/{cid}/entities", json={"value": "Valencia, Spain", "type": "location"}).json()
    assert "_lat" not in named["entity"]["props"]
