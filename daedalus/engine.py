"""Transform runner: jobs, live events, result limits and machines."""

from __future__ import annotations

import asyncio
import ipaddress
import logging
import socket
import time
import traceback
import uuid
from pathlib import Path
from urllib.parse import urlparse

import httpx

from .config import API_KEYS, Settings
from .store import Store
from .transforms import MACHINES, REGISTRY, Skip, Transform

log = logging.getLogger("daedalus")

USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"


def make_client(transport: httpx.AsyncBaseTransport | None = None) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        timeout=httpx.Timeout(20.0, connect=10.0),
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9,es;q=0.8"},
        limits=httpx.Limits(max_connections=80, max_keepalive_connections=40),
        transport=transport,
    )


class Job:
    """A batch of transform runs whose progress is streamed to the browser."""

    def __init__(self, case_id: int, kind: str):
        self.id = uuid.uuid4().hex[:12]
        self.case_id = case_id
        self.kind = kind
        self.events: list[dict] = []
        self.done = False
        self.cancelled = False
        self.created: list[str] = []
        self.started = time.time()
        self._new = asyncio.Event()
        self.task: asyncio.Task | None = None

    def emit(self, event: dict) -> None:
        self.events.append(event)
        self._new.set()

    def finish(self) -> None:
        self.done = True
        self._new.set()

    def cancel(self) -> None:
        self.cancelled = True
        if self.task and not self.task.done():
            self.task.cancel()

    async def stream(self):
        i = 0
        while True:
            if i < len(self.events):
                i += 1
                yield self.events[i - 1]
                continue
            if self.done:
                return
            self._new.clear()
            try:
                await asyncio.wait_for(self._new.wait(), 15)
            except asyncio.TimeoutError:
                yield None  # keep-alive


class Context:
    """What a transform sees while it runs on one entity."""

    def __init__(self, engine: "Engine", job: Job, entity: dict, transform: Transform, limit: int):
        self.engine = engine
        self.job = job
        self.case_id = job.case_id
        self.entity = entity
        self.value: str = entity["value"]
        self.props: dict = entity.get("props") or {}
        self.transform = transform
        self.http: httpx.AsyncClient = engine.http
        self.settings: Settings = engine.settings
        self.limit = limit
        self.found = 0
        self.truncated = False
        self.enriched = False
        self.message = ""
        self.new_ids: list[str] = []

    # ----------------------------------------------------------------- keys
    def key(self, name: str) -> str | None:
        return self.settings.key(name)

    def require_key(self, name: str) -> str:
        k = self.settings.key(name)
        if not k:
            label, url = API_KEYS[name]
            raise Skip(f"API key required: {label} ({url})")
        return k

    # -------------------------------------------------------------- results
    def add(self, etype: str, value, props: dict | None = None, label: str = "", parent: str | None = None,
            reverse: bool = False) -> str | None:
        """Add (or merge) an entity and link it to the input entity (or `parent`).

        `label` names the link; with reverse=True the link points from the new entity to the parent.
        Returns the entity id, or None once the result limit is reached.
        """
        value = str(value or "").strip()
        if not value:
            return None
        if self.found >= self.limit:
            self.truncated = True
            return None
        props = dict(props or {})
        props["_sources"] = [self.transform.title["en"]]
        ent, created = self.engine.store.upsert_entity(self.case_id, etype, value, props)
        anchor = parent or self.entity["id"]
        self.job.emit({"type": "entity", "entity": ent, "created": created, "parent": anchor})
        if created:
            self.job.created.append(ent["id"])
        src, dst = (ent["id"], anchor) if reverse else (anchor, ent["id"])
        if src != dst and self.engine.store.add_link(self.case_id, src, dst, label or "related", self.transform.name):
            self.job.emit({"type": "link", "link": {"src": src, "dst": dst, "label": label or "related",
                                                     "transform": self.transform.name}})
        self.found += 1
        if ent["id"] not in self.new_ids and ent["id"] != self.entity["id"]:
            self.new_ids.append(ent["id"])
        return ent["id"]

    def enrich(self, props: dict, eid: str | None = None) -> None:
        """Merge properties into the input entity (or `eid`)."""
        props = {k: v for k, v in props.items() if v not in (None, "", [], {})}
        if not props:
            return
        props["_sources"] = [self.transform.title["en"]]
        ent = self.engine.store.update_entity(self.case_id, eid or self.entity["id"], props=props)
        if ent:
            self.job.emit({"type": "entity", "entity": ent, "created": False})
            self.enriched = True

    def log(self, message: str) -> None:
        self.message = message

    # ----------------------------------------------------------------- HTTP
    async def get_json(self, url: str, **kw) -> tuple[int, object]:
        """GET returning (status, parsed JSON or None); never raises on HTTP status codes."""
        r = await self.http.get(url, **kw)
        try:
            data = r.json()
        except ValueError:
            data = None
        return r.status_code, data

    async def assert_public(self, url: str) -> None:
        """SSRF guard: refuse URLs pointing at private, loopback or link-local addresses."""
        if not self.settings.get("block_private_targets", True):
            return
        host = urlparse(url).hostname or ""
        try:
            infos = await asyncio.to_thread(socket.getaddrinfo, host, None)
            addrs = {i[4][0] for i in infos}
        except OSError:
            return  # unresolvable: the request will fail on its own
        for a in addrs:
            ip = ipaddress.ip_address(a.split("%")[0])
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
                raise Skip(f"Blocked private address {a} (disable 'block private targets' in settings to allow)")


class Engine:
    def __init__(self, store: Store, settings: Settings, data_dir: Path):
        self.store = store
        self.settings = settings
        self.data_dir = data_dir
        self.http: httpx.AsyncClient | None = None
        self.jobs: dict[str, Job] = {}

    async def start(self, transport: httpx.AsyncBaseTransport | None = None) -> None:
        if self.http is None:
            self.http = make_client(transport)

    async def stop(self) -> None:
        for job in self.jobs.values():
            job.cancel()
        if self.http:
            await self.http.aclose()
            self.http = None

    def transforms_for(self, entity: dict) -> list[Transform]:
        return [t for t in REGISTRY.values() if t.applies(entity)]

    def _new_job(self, case_id: int, kind: str) -> Job:
        job = Job(case_id, kind)
        self.jobs[job.id] = job
        finished = [j for j, jb in self.jobs.items() if jb.done]
        for jid in finished[:-30]:
            self.jobs.pop(jid, None)
        return job

    def _limit(self, limit: int | None) -> int:
        lim = limit or self.settings.get("result_limit", 50)
        return max(1, min(int(lim), 1000))

    # -------------------------------------------------------------- public API
    def run_transforms(self, case_id: int, entity_ids: list[str], transforms: list[str] | None,
                       limit: int | None = None) -> Job:
        """Run the given transforms (None = all default ones) on each entity they apply to."""
        job = self._new_job(case_id, "transforms")
        job.task = asyncio.create_task(self._guard(job, self._transforms_job(job, entity_ids, transforms,
                                                                             self._limit(limit))))
        return job

    def run_machine(self, case_id: int, entity_ids: list[str], machine: str, depth: int = 2,
                    limit: int | None = None) -> Job:
        job = self._new_job(case_id, "machine")
        job.task = asyncio.create_task(self._guard(job, self._machine_job(job, entity_ids, machine, depth,
                                                                          self._limit(limit))))
        return job

    # ------------------------------------------------------------------ internals
    async def _guard(self, job: Job, coro) -> None:
        try:
            await coro
            job.emit({"type": "done", "created": len(job.created), "seconds": round(time.time() - job.started, 1)})
        except asyncio.CancelledError:
            job.emit({"type": "done", "created": len(job.created), "cancelled": True,
                      "seconds": round(time.time() - job.started, 1)})
        except Exception as e:  # noqa: BLE001
            log.error("job %s failed: %s", job.id, traceback.format_exc())
            job.emit({"type": "error", "message": f"{type(e).__name__}: {e}"})
        finally:
            self.store.touch(job.case_id)
            job.finish()

    async def _transforms_job(self, job: Job, entity_ids: list[str], names: list[str] | None, limit: int) -> None:
        if names:
            chosen = [REGISTRY[n] for n in names if n in REGISTRY]
        else:
            chosen = [t for t in REGISTRY.values() if t.default]
        pairs = []
        for eid in dict.fromkeys(entity_ids):
            ent = self.store.get_entity(job.case_id, eid)
            if ent:
                pairs += [(ent, t) for t in chosen if t.applies(ent)]
        job.emit({"type": "plan", "runs": len(pairs)})
        await self._run_pairs(job, pairs, limit)

    async def _run_pairs(self, job: Job, pairs: list[tuple[dict, Transform]], limit: int) -> list[Context]:
        sem = asyncio.Semaphore(10)

        async def one(ent, t):
            async with sem:
                return await self._run_one(job, ent, t, limit)

        return list(await asyncio.gather(*(one(e, t) for e, t in pairs)))

    async def _run_one(self, job: Job, ent: dict, t: Transform, limit: int) -> Context:
        ctx = Context(self, job, ent, t, limit)
        job.emit({"type": "run_start", "entity_id": ent["id"], "transform": t.name})
        started = time.time()
        try:
            for k in t.keys:
                ctx.require_key(k)
            await asyncio.wait_for(t.run(ctx), t.timeout)
            status = "ok" if (ctx.found or ctx.enriched) else "empty"
            if ctx.message:
                msg = ctx.message
            elif ctx.found:
                msg = f"{ctx.found} result(s)" + (" · limit reached" if ctx.truncated else "")
            else:
                msg = "Properties updated" if ctx.enriched else "No results"
        except Skip as e:
            status, msg = "skipped", str(e)
        except asyncio.TimeoutError:
            status, msg = "error", f"Timed out after {int(t.timeout)} s" + (f" · {ctx.found} partial" if ctx.found else "")
        except httpx.HTTPError as e:
            status, msg = "error", f"Network error: {type(e).__name__}"
        except asyncio.CancelledError:
            self.store.add_run(job.case_id, ent["id"], t.name, "error", "Cancelled", ctx.found, started)
            raise
        except Exception as e:  # noqa: BLE001
            log.error("transform %s failed: %s", t.name, traceback.format_exc())
            status, msg = "error", f"{type(e).__name__}: {e}"
        run = self.store.add_run(job.case_id, ent["id"], t.name, status, msg, ctx.found, started)
        job.emit({"type": "run", "run": run})
        return ctx

    async def _machine_job(self, job: Job, seeds: list[str], name: str, depth: int, limit: int) -> None:
        machine = MACHINES.get(name)
        if not machine:
            raise ValueError(f"Unknown machine {name}")
        budget = int(self.settings.get("machine_max_entities", 60))
        frontier = [s for s in dict.fromkeys(seeds) if self.store.get_entity(job.case_id, s)]
        done: set[tuple[str, str]] = set()
        expanded: set[str] = set()
        stages = machine.stages(depth)
        job.emit({"type": "plan", "machine": name, "stages": len(stages)})
        for i, stage in enumerate(stages):
            if job.cancelled or not frontier:
                break
            pairs = []
            for eid in frontier:
                ent = self.store.get_entity(job.case_id, eid)
                if not ent:
                    continue
                if eid not in expanded:
                    if len(expanded) >= budget:
                        continue
                    expanded.add(eid)
                for tname in stage:
                    t = REGISTRY.get(tname)
                    if t and t.applies(ent) and (eid, tname) not in done:
                        done.add((eid, tname))
                        pairs.append((ent, t))
            job.emit({"type": "stage", "index": i, "runs": len(pairs), "frontier": len(frontier)})
            ctxs = await self._run_pairs(job, pairs, limit)
            produced: list[str] = []
            for c in ctxs:
                produced += [x for x in c.new_ids if x not in produced]
            frontier = produced if machine.chain else list(dict.fromkeys(frontier + produced))
