"""HTTP API and static web app."""

from __future__ import annotations

import asyncio
import base64
import csv
import io
import json
import os
import re
import secrets
import time
from contextlib import asynccontextmanager
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape

import httpx
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import __version__, graphalgo
from .config import LANGUAGES, WEB_DIR, Settings, default_data_dir
from .engine import Engine
from .entities import CATEGORIES, ENTITY_TYPES, detect_type, entity_id, normalize
from .exif import analyze_image
from .store import Store
from .transforms import MACHINES, REGISTRY, TRANSFORM_CATEGORIES, load_plugins


class CaseIn(BaseModel):
    name: str | None = None
    notes: str | None = None
    layout: dict | None = None


class EntityIn(BaseModel):
    value: str
    type: str | None = None
    props: dict | None = None
    notes: str | None = None
    parent: str | None = None
    label: str | None = None


class EntityUpdate(BaseModel):
    id: str
    value: str | None = None
    props: dict | None = None
    replace: dict | None = None
    notes: str | None = None
    bookmark: str | None = None


class IdsIn(BaseModel):
    ids: list[str]


class MergeIn(BaseModel):
    keep: str
    drop: list[str]


class LinkIn(BaseModel):
    src: str
    dst: str
    label: str = "related"


class RunIn(BaseModel):
    entity_ids: list[str]
    transforms: list[str] | None = None
    limit: int | None = None


class MachineIn(BaseModel):
    entity_ids: list[str]
    machine: str
    depth: int = 2
    limit: int | None = None


class PathsIn(BaseModel):
    src: str
    dst: str
    k: int = Field(5, ge=1, le=25)
    max_len: int | None = Field(None, ge=1, le=30)
    directed: bool = False


class ConnectIn(BaseModel):
    ids: list[str]
    directed: bool = False


class DetectIn(BaseModel):
    value: str


def _slug(name: str) -> str:
    return re.sub(r"_+", "_", "".join(ch if ch.isalnum() else "_" for ch in name))[:40].strip("_") or "case"


def graphml(case: dict, graph: dict) -> str:
    out = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<graphml xmlns="http://graphml.graphdrawing.org/xmlns">',
        '  <key id="type" for="node" attr.name="type" attr.type="string"/>',
        '  <key id="value" for="node" attr.name="value" attr.type="string"/>',
        '  <key id="label" for="node" attr.name="label" attr.type="string"/>',
        '  <key id="props" for="node" attr.name="properties" attr.type="string"/>',
        '  <key id="elabel" for="edge" attr.name="label" attr.type="string"/>',
        '  <key id="transform" for="edge" attr.name="transform" attr.type="string"/>',
        f'  <graph id="{xml_escape(_slug(case["name"]))}" edgedefault="directed">',
    ]
    for e in graph["entities"]:
        out.append(f'    <node id="{xml_escape(e["id"], {chr(34): "&quot;"})}">')
        for key, val in (("type", e["type"]), ("value", e["value"]), ("label", e["label"]),
                         ("props", json.dumps(e["props"], ensure_ascii=False, default=str))):
            out.append(f'      <data key="{key}">{xml_escape(str(val))}</data>')
        out.append("    </node>")
    for i, ln in enumerate(graph["links"]):
        q = {chr(34): "&quot;"}
        out.append(f'    <edge id="e{i}" source="{xml_escape(ln["src"], q)}" target="{xml_escape(ln["dst"], q)}">')
        out.append(f'      <data key="elabel">{xml_escape(ln["label"])}</data>')
        out.append(f'      <data key="transform">{xml_escape(ln.get("transform") or "")}</data>')
        out.append("    </edge>")
    out += ["  </graph>", "</graphml>"]
    return "\n".join(out)


def create_app(data_dir: Path | None = None, transport: httpx.AsyncBaseTransport | None = None,
               password: str | None = None) -> FastAPI:
    data_dir = Path(data_dir or default_data_dir())
    data_dir.mkdir(parents=True, exist_ok=True)
    settings = Settings(data_dir / "settings.json")
    store = Store(data_dir / "daedalus.db")
    engine = Engine(store, settings, data_dir)
    plugins = load_plugins(data_dir / "plugins")
    password = password if password is not None else os.environ.get("DAEDALUS_PASSWORD", "")

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        await engine.start(transport)
        yield
        await engine.stop()

    app = FastAPI(title="DAEDALUS", version=__version__, lifespan=lifespan)
    app.state.store, app.state.settings, app.state.engine = store, settings, engine

    if password:
        expected = "Basic " + base64.b64encode(f"daedalus:{password}".encode()).decode()

        @app.middleware("http")
        async def basic_auth(request: Request, call_next):
            if request.url.path == "/healthz":  # platform health checks carry no credentials
                return await call_next(request)
            given = request.headers.get("authorization", "")
            ok = secrets.compare_digest(given.encode(), expected.encode())
            if not ok and given.lower().startswith("basic "):
                try:  # accept any user name, only the password matters
                    _, _, pw = base64.b64decode(given[6:]).decode().partition(":")
                    ok = secrets.compare_digest(pw.encode(), password.encode())
                except (ValueError, UnicodeDecodeError):
                    ok = False
            if not ok:
                if given:
                    await asyncio.sleep(1)  # slow down password guessing
                return Response("Authentication required", status_code=401,
                                headers={"WWW-Authenticate": 'Basic realm="DAEDALUS"'})
            return await call_next(request)

    @app.middleware("http")
    async def no_cache_static(request: Request, call_next):
        response = await call_next(request)
        if not request.url.path.startswith(("/api/", "/vendor/")):
            response.headers.setdefault("Cache-Control", "no-cache")
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        return response

    def case_or_404(case_id: int) -> dict:
        c = store.get_case(case_id)
        if not c:
            raise HTTPException(404, "Case not found")
        return c

    def entity_or_404(case_id: int, eid: str) -> dict:
        e = store.get_entity(case_id, eid)
        if not e:
            raise HTTPException(404, "Entity not found")
        return e

    # ------------------------------------------------------------------ meta
    @app.get("/healthz")
    def healthz():
        return {"ok": True, "version": __version__}

    @app.get("/api/meta")
    def meta():
        return {
            "version": __version__,
            "entity_types": ENTITY_TYPES,
            "entity_categories": CATEGORIES,
            "transform_categories": TRANSFORM_CATEGORIES,
            "transforms": [{**t.meta(), "ready": all(settings.key(k) for k in t.keys)} for t in REGISTRY.values()],
            "machines": [m.meta() for m in MACHINES.values()],
            "languages": LANGUAGES,
            "auth": bool(password),
            "plugins": plugins,
        }

    @app.post("/api/detect")
    def detect(body: DetectIn):
        return {"type": detect_type(body.value)}

    @app.get("/api/settings")
    def get_settings():
        return settings.public()

    @app.put("/api/settings")
    def put_settings(body: dict):
        settings.update(body)
        return settings.public()

    # ----------------------------------------------------------------- cases
    @app.get("/api/cases")
    def list_cases():
        return store.list_cases()

    @app.post("/api/cases")
    def create_case(body: CaseIn):
        return store.create_case(body.name or "", body.notes or "")

    @app.get("/api/cases/{case_id}")
    def get_case(case_id: int):
        return {"case": case_or_404(case_id), **store.graph(case_id)}

    @app.patch("/api/cases/{case_id}")
    def update_case(case_id: int, body: CaseIn):
        case_or_404(case_id)
        return store.update_case(case_id, name=body.name, notes=body.notes, layout=body.layout)

    @app.delete("/api/cases/{case_id}")
    def delete_case(case_id: int):
        case_or_404(case_id)
        store.delete_case(case_id)
        return {"ok": True}

    # -------------------------------------------------------------- entities
    @app.post("/api/cases/{case_id}/entities")
    def add_entity(case_id: int, body: EntityIn):
        case_or_404(case_id)
        value = body.value.strip()
        if not value:
            raise HTTPException(400, "Empty value")
        etype = body.type or detect_type(value)
        if etype not in ENTITY_TYPES:
            raise HTTPException(400, f"Unknown entity type {etype}")
        parent = entity_or_404(case_id, body.parent) if body.parent else None
        props = dict(body.props or {})
        props.setdefault("_sources", ["Manual"])
        ent, created = store.upsert_entity(case_id, etype, value, props, root=not parent)
        if body.notes is not None:
            ent = store.update_entity(case_id, ent["id"], notes=body.notes)
        link = None
        if parent and parent["id"] != ent["id"]:
            label = " ".join((body.label or "related").split())[:80]
            store.add_link(case_id, parent["id"], ent["id"], label, "manual")
            link = {"src": parent["id"], "dst": ent["id"], "label": label, "transform": "manual"}
        store.touch(case_id)
        return {"entity": ent, "created": created, "link": link}

    @app.post("/api/cases/{case_id}/entities/update")
    def update_entity(case_id: int, body: EntityUpdate):
        case_or_404(case_id)
        ent = entity_or_404(case_id, body.id)
        renamed_from = None
        if body.value is not None and normalize(ent["type"], body.value) != ent["value"]:
            if not body.value.strip():
                raise HTTPException(400, "Empty value")
            new_id = entity_id(ent["type"], normalize(ent["type"], body.value))
            target, _ = store.upsert_entity(case_id, ent["type"], body.value, {}, root=ent["root"])
            if target["id"] != ent["id"]:
                store.merge_entities(case_id, new_id, [ent["id"]])
                renamed_from = ent["id"]
                ent = target
        out = store.update_entity(case_id, ent["id"], props=body.props, replace=body.replace, notes=body.notes,
                                  bookmark=body.bookmark)
        store.touch(case_id)
        return {"entity": out, "renamed_from": renamed_from,
                "links": store.links(case_id) if renamed_from else None}

    @app.post("/api/cases/{case_id}/entities/delete")
    def delete_entities(case_id: int, body: IdsIn):
        case_or_404(case_id)
        n = store.delete_entities(case_id, body.ids[:50000])
        store.touch(case_id)
        return {"deleted": n}

    @app.post("/api/cases/{case_id}/entities/merge")
    def merge_entities(case_id: int, body: MergeIn):
        case_or_404(case_id)
        entity_or_404(case_id, body.keep)
        ent = store.merge_entities(case_id, body.keep, body.drop)
        store.touch(case_id)
        return {"entity": ent, "links": store.links(case_id)}

    @app.post("/api/cases/{case_id}/links")
    def add_link(case_id: int, body: LinkIn):
        case_or_404(case_id)
        if body.src == body.dst:
            raise HTTPException(400, "A link needs two different entities")
        entity_or_404(case_id, body.src)
        entity_or_404(case_id, body.dst)
        label = " ".join(body.label.split())[:80] or "related"
        store.add_link(case_id, body.src, body.dst, label, "manual")
        store.touch(case_id)
        return {"src": body.src, "dst": body.dst, "label": label, "transform": "manual"}

    @app.post("/api/cases/{case_id}/links/delete")
    def delete_link(case_id: int, body: LinkIn):
        case_or_404(case_id)
        return {"ok": store.delete_link(case_id, body.src, body.dst, body.label)}

    @app.get("/api/cases/{case_id}/runs")
    def runs(case_id: int, entity: str | None = None):
        case_or_404(case_id)
        return store.runs(case_id, entity)

    # ------------------------------------------------------------ transforms
    @app.post("/api/cases/{case_id}/run")
    async def run_transforms(case_id: int, body: RunIn):
        case_or_404(case_id)
        unknown = [t for t in body.transforms or [] if t not in REGISTRY]
        if unknown:
            raise HTTPException(400, f"Unknown transform(s): {', '.join(unknown)}")
        job = engine.run_transforms(case_id, body.entity_ids, body.transforms, body.limit)
        return {"job_id": job.id}

    @app.post("/api/cases/{case_id}/machine")
    async def run_machine(case_id: int, body: MachineIn):
        case_or_404(case_id)
        if body.machine not in MACHINES:
            raise HTTPException(400, "Unknown machine")
        job = engine.run_machine(case_id, body.entity_ids, body.machine, body.depth, body.limit)
        return {"job_id": job.id}

    @app.get("/api/jobs/{job_id}/events")
    async def job_events(job_id: str):
        job = engine.jobs.get(job_id)
        if not job:
            raise HTTPException(404, "Job not found")

        async def gen():
            async for ev in job.stream():
                if ev is None:
                    yield ": ping\n\n"
                else:
                    yield f"data: {json.dumps(ev, ensure_ascii=False, default=str)}\n\n"

        return StreamingResponse(gen(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    @app.post("/api/jobs/{job_id}/cancel")
    def cancel_job(job_id: str):
        job = engine.jobs.get(job_id)
        if not job:
            raise HTTPException(404, "Job not found")
        job.cancel()
        return {"ok": True}

    # -------------------------------------------------------------- analysis
    @app.post("/api/cases/{case_id}/paths")
    def paths(case_id: int, body: PathsIn):
        case_or_404(case_id)
        g = graphalgo.Graph.from_case(store.graph(case_id))
        for eid in (body.src, body.dst):
            if eid not in g.out:
                raise HTTPException(404, "Entity not found")
        found = graphalgo.k_shortest_paths(g, body.src, body.dst, body.k, body.max_len, body.directed)
        return {"paths": [{"nodes": p, "length": len(p) - 1, "hops": g.path_edges(p)} for p in found]}

    @app.post("/api/cases/{case_id}/connect")
    def connect(case_id: int, body: ConnectIn):
        case_or_404(case_id)
        g = graphalgo.Graph.from_case(store.graph(case_id))
        return graphalgo.connect(g, body.ids, body.directed)

    @app.get("/api/cases/{case_id}/analysis")
    def analysis(case_id: int):
        case_or_404(case_id)
        return graphalgo.analyze(store.graph(case_id))

    @app.post("/api/cases/{case_id}/similar")
    def similar(case_id: int, body: IdsIn):
        case_or_404(case_id)
        g = graphalgo.Graph.from_case(store.graph(case_id))
        return {"similar": graphalgo.similar_to(g, body.ids[0]) if body.ids else []}

    # ------------------------------------------------------ upload / export
    @app.post("/api/cases/{case_id}/upload")
    async def upload(case_id: int, file: UploadFile = File(...)):
        case_or_404(case_id)
        data = await file.read(40 * 1024 * 1024 + 1)
        if len(data) > 40 * 1024 * 1024:
            raise HTTPException(413, "File too large (40 MB max)")
        try:
            info = analyze_image(data, os.path.basename(file.filename or "image"))
        except Exception as e:  # noqa: BLE001
            raise HTTPException(400, f"Not a readable image: {e}") from e
        info["_sources"] = ["EXIF"]
        img, _ = store.upsert_entity(case_id, "image", info["sha256"], info, root=True)
        h, _ = store.upsert_entity(case_id, "hash", info["sha256"], {"algorithm": "SHA-256", "_sources": ["EXIF"]})
        store.add_link(case_id, img["id"], h["id"], "SHA-256", "exif")
        if "_lat" in info:
            lat, lon = info["_lat"], info["_lon"]
            loc, _ = store.upsert_entity(case_id, "location", f"{lat}, {lon}", {
                "_lat": lat, "_lon": lon, "precision": "photo GPS", "_sources": ["EXIF"],
                "_links": [["OpenStreetMap", f"https://www.openstreetmap.org/?mlat={lat}&mlon={lon}#map=17/{lat}/{lon}"]]})
            store.add_link(case_id, img["id"], loc["id"], "taken at", "exif")
        for key in ("artist", "windows_author", "camera_owner", "copyright"):
            if info.get(key) and len(info[key]) > 2:
                p, _ = store.upsert_entity(case_id, "person", info[key], {"_sources": ["EXIF"]})
                store.add_link(case_id, img["id"], p["id"], key.replace("_", " "), "exif")
        store.touch(case_id)
        return {"entity": store.get_entity(case_id, img["id"])}

    @app.get("/api/cases/{case_id}/export")
    def export(case_id: int, format: str = "json"):  # noqa: A002
        case = case_or_404(case_id)
        graph = store.graph(case_id)
        name = _slug(case["name"])
        if format == "graphml":
            return Response(graphml(case, graph), media_type="application/graphml+xml",
                            headers={"Content-Disposition": f'attachment; filename="daedalus_{name}.graphml"'})
        if format in ("csv", "links-csv"):
            buf = io.StringIO()
            w = csv.writer(buf)
            if format == "csv":
                w.writerow(["id", "type", "value", "label", "bookmark", "notes", "properties"])
                for e in graph["entities"]:
                    props = {k: v for k, v in e["props"].items() if not k.startswith("_")}
                    w.writerow([e["id"], e["type"], e["value"], e["label"], e["bookmark"], e["notes"],
                                json.dumps(props, ensure_ascii=False, default=str)])
            else:
                w.writerow(["source", "target", "label", "transform"])
                for ln in graph["links"]:
                    w.writerow([ln["src"], ln["dst"], ln["label"], ln.get("transform") or ""])
            suffix = "entities" if format == "csv" else "links"
            return Response(buf.getvalue(), media_type="text/csv",
                            headers={"Content-Disposition": f'attachment; filename="daedalus_{name}_{suffix}.csv"'})
        payload = {"daedalus": __version__, "exported": time.strftime("%Y-%m-%dT%H:%M:%S"), "case": case,
                   "entities": graph["entities"], "links": graph["links"]}
        return Response(json.dumps(payload, ensure_ascii=False, indent=1, default=str), media_type="application/json",
                        headers={"Content-Disposition": f'attachment; filename="daedalus_{name}.json"'})

    @app.post("/api/import")
    async def import_case(file: UploadFile = File(...)):
        try:
            data = json.loads(await file.read(200 * 1024 * 1024))
            src = data["case"]
            entities, links = data.get("entities") or [], data.get("links") or data.get("edges") or []
        except (ValueError, KeyError, TypeError) as e:
            raise HTTPException(400, "Not a DAEDALUS export") from e
        case = store.create_case(f"{src.get('name') or 'Imported'} (imported)", src.get("notes") or "")
        ids: dict[str, str] = {}
        for e in entities:
            etype = e.get("type")
            if etype not in ENTITY_TYPES or not e.get("value"):
                continue
            ent, _ = store.upsert_entity(case["id"], etype, e["value"], e.get("props") or e.get("attrs") or {},
                                         root=bool(e.get("root")))
            if e.get("notes") or e.get("bookmark"):
                store.update_entity(case["id"], ent["id"], notes=e.get("notes"), bookmark=e.get("bookmark"))
            ids[e.get("id") or ent["id"]] = ent["id"]
        for ln in links:
            a, b = ids.get(ln.get("src")), ids.get(ln.get("dst"))
            if a and b:
                store.add_link(case["id"], a, b, ln.get("label") or "related", ln.get("transform") or "import")
        if isinstance(src.get("layout"), dict):
            store.update_case(case["id"], layout=src["layout"])
        return store.get_case(case["id"])

    @app.exception_handler(ValueError)
    async def value_error(_request: Request, exc: ValueError):
        return JSONResponse({"detail": str(exc)}, status_code=400)

    # --------------------------------------------------------------- web app
    @app.get("/")
    def index():
        html = (WEB_DIR / "index.html").read_text(encoding="utf-8")
        return Response(html.replace("__VERSION__", __version__), media_type="text/html",
                        headers={"Cache-Control": "no-cache"})

    app.mount("/", StaticFiles(directory=WEB_DIR), name="web")
    return app
