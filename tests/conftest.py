import asyncio
import json
import re

import httpx
import pytest

from daedalus.config import Settings
from daedalus.engine import Engine, Job
from daedalus.store import Store
from daedalus.transforms import REGISTRY


class Router:
    """httpx mock transport: first regex matching "METHOD url" wins; unmatched requests get a 404."""

    def __init__(self):
        self.routes: list[tuple[re.Pattern, object]] = []
        self.calls: list[str] = []

    def add(self, pattern: str, response=None, *, json_body=None, text=None, status=200, headers=None):
        if response is None:
            if json_body is not None:
                response = httpx.Response(status, json=json_body, headers=headers)
            else:
                response = httpx.Response(status, text=text or "", headers=headers)
        self.routes.append((re.compile(pattern), response))
        return self

    def __call__(self, request: httpx.Request) -> httpx.Response:
        key = f"{request.method} {request.url}"
        self.calls.append(key)
        for rx, resp in self.routes:
            if rx.search(key):
                if callable(resp):
                    return resp(request)
                return httpx.Response(resp.status_code, content=resp.content, headers=resp.headers)
        return httpx.Response(404, json={"detail": "not mocked"})

    @property
    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self)


@pytest.fixture
def router():
    return Router()


@pytest.fixture
def engine_env(tmp_path):
    """(store, settings, make_engine) bound to a temporary data dir."""
    store = Store(tmp_path / "t.db")
    settings = Settings(tmp_path / "settings.json")
    settings.update({"block_private_targets": False})

    async def make(router: Router) -> Engine:
        eng = Engine(store, settings, tmp_path)
        await eng.start(router.transport)
        return eng

    yield store, settings, make
    store.close()


def run_transform(engine_env, router, name: str, etype: str, value: str, props: dict | None = None, limit: int = 50):
    """Run one transform synchronously on a fresh case; returns (graph, run_record, job)."""
    store, _settings, make = engine_env

    async def go():
        eng = await make(router)
        case = store.create_case("t")
        ent, _ = store.upsert_entity(case["id"], etype, value, props or {}, root=True)
        job = Job(case["id"], "test")
        ctx = await eng._run_one(job, ent, REGISTRY[name], limit)
        await eng.stop()
        return case["id"], ctx, job

    case_id, ctx, job = asyncio.run(go())
    runs = store.runs(case_id)
    return store.graph(case_id), runs[-1], job


def values(graph, etype):
    return sorted(e["value"] for e in graph["entities"] if e["type"] == etype)


def dumps(x):
    return json.dumps(x)
