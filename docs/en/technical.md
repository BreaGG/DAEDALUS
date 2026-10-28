# DAEDALUS technical documentation

Author: **Alejandro Brea**

How DAEDALUS is built, how to run and deploy it, its HTTP API, and how to extend it with your own transforms.
For day-to-day use of the interface, see the [user guide](user-guide.md); for the list of entities, transforms and
machines, see the [reference](transforms.md).

**Contents**

1. [Architecture](#1-architecture)
2. [Installation](#2-installation)
3. [Running and configuration](#3-running-and-configuration)
4. [Deployment](#4-deployment)
5. [Security model](#5-security-model)
6. [Data model](#6-data-model)
7. [Transform engine](#7-transform-engine)
8. [HTTP API](#8-http-api)
9. [Graph algorithms](#9-graph-algorithms)
10. [Extending DAEDALUS](#10-extending-daedalus)
11. [Frontend](#11-frontend)
12. [Development](#12-development)

---

## 1. Architecture

```
 Browser (single-page app, no build step)
   │  REST (JSON)            ▲ Server-Sent Events (live job progress)
   ▼                         │
 FastAPI app ── api.py ──────┤
   │                         │
   ├── engine.py ── async jobs ── transforms/* ──► public sources & APIs (httpx, DNS, WHOIS)
   ├── graphalgo.py  (paths, centrality, communities, choke points)
   └── store.py ──► SQLite (daedalus.db, WAL)     settings.json     plugins/*.py
```

- **One process.** The web server, the job runner and the database live in a single Python process
  (FastAPI + uvicorn, asyncio). Jobs are kept in memory, so **run exactly one instance**.
- **Backend** (`daedalus/`): Python ≥ 3.11 with FastAPI, httpx, dnspython, phonenumbers and Pillow. No external
  services are needed besides the OSINT sources themselves.
- **Frontend** (`daedalus/web/`): plain ES modules with vendored Cytoscape.js (graph), fcose/dagre (layouts) and
  Leaflet (map). It works offline except for map tiles.

| Module | Responsibility |
|---|---|
| `__main__.py` | CLI entry point, hosting guard rails (port, password, volume, privilege drop). |
| `api.py` | `create_app()`: HTTP routes, optional Basic auth, static files, import/export. |
| `engine.py` | Jobs, the per-run `Context` given to transforms, result limits, machines, SSRF guard. |
| `store.py` | SQLite persistence of investigations, entities, links and runs. |
| `entities.py` | Entity catalogue, type detection, normalisation and ids. |
| `graphalgo.py` | Dependency-free graph algorithms. |
| `transforms/` | Built-in transforms by family, the registry, machines and the plugin loader. |
| `config.py` | Paths, settings persistence, API key catalogue, languages. |
| `exif.py` | Photo metadata extraction. |
| `webutil.py` | HTML parsing, social-profile URL patterns, DNS helpers. |

## 2. Installation

```bash
git clone https://github.com/BreaGG/DAEDALUS.git && cd DAEDALUS
python3 -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -e .            # or: pip install -e ".[dev]" for pytest + ruff
```

`start.sh` / `start.bat` do the same (create `.venv`, install `requirements.txt`) and launch the app.
The package is also buildable as a wheel (`pip wheel .`); the web assets ship inside it.

## 3. Running and configuration

```bash
daedalus [--host HOST] [--port PORT] [--data-dir DIR] [--no-browser]
python -m daedalus ...        # same thing
```

### Options and environment variables

| CLI flag | Environment variable | Default | Meaning |
|---|---|---|---|
| `--host` | `DAEDALUS_HOST` | `127.0.0.1` | Interface to bind. `0.0.0.0` exposes it on the network (set a password). |
| `--port` | `DAEDALUS_PORT`, then `PORT` | `8787` | Listening port. `PORT` is what Railway, Render, Fly… inject. |
| `--data-dir` | see below | see below | Where investigations and settings are stored. |
| `--no-browser` | — | off | Do not open a browser tab on start. |
| — | `DAEDALUS_PASSWORD` | empty | Enables HTTP Basic auth for the whole app (any user name, this password). |
| — | `DAEDALUS_ALLOW_PUBLIC` | — | `1` lets the app start on Railway without a password (not recommended). |
| — | `DAEDALUS_RUN_AS` | — | When started as root, take ownership of the data dir and switch to this user (the Docker image sets `daedalus`). |

### Data directory

Resolved in this order, first match wins:

1. `--data-dir`
2. `DAEDALUS_DATA_DIR`
3. `RAILWAY_VOLUME_MOUNT_PATH` (set by Railway when a volume is attached)
4. `DAEDALUS_DEFAULT_DATA_DIR` (`/data` in the Docker image)
5. `./data` next to a source checkout
6. `~/.daedalus`

Contents:

| File | What |
|---|---|
| `daedalus.db` (+ `-wal`, `-shm`) | SQLite database with every investigation. |
| `settings.json` | Settings that differ from the defaults, **including API keys in plain text**. |
| `plugins/*.py` | Your own transforms and machines (loaded at start-up). |
| `sherlock.json` | Cache of the Sherlock site list, when that option is enabled. |

**Backups**: copy the folder while DAEDALUS is stopped, or use `sqlite3 daedalus.db ".backup backup.db"` while it
runs. Individual investigations can be exported as JSON from the interface (or `GET /api/cases/{id}/export`).
**Upgrading**: pull the new version and restart; tables are created if missing and existing data is kept.

## 4. Deployment

DAEDALUS needs a long-running process with a persistent disk, a single instance, and outbound internet access
(HTTPS, DNS on 53 and WHOIS on TCP 43). Serverless platforms such as Vercel or Netlify Functions do not fit:
jobs continue after the HTTP response, progress is streamed from memory and the database is a file.

### Local

`./start.sh` (or `daedalus`). It listens on `127.0.0.1:8787`, only reachable from your machine.

### Docker Compose

```bash
DAEDALUS_PASSWORD='a-long-random-string' docker compose up -d --build
```

The provided `docker-compose.yml` publishes the port on `127.0.0.1` only and mounts `./data` at `/data`. The image
starts as root just long enough to take ownership of the mounted volume, then runs as the unprivileged `daedalus`
user. The container exposes a `HEALTHCHECK` on `/healthz`.

### Railway

The repository includes `railway.toml` (Dockerfile build, `/healthz` health check, one replica, app sleeping off).

1. **New Project → Deploy from GitHub repo** and select the repository (and the branch you want to deploy).
2. **Variables**: add `DAEDALUS_PASSWORD` (e.g. `openssl rand -base64 24`). Without it the app exits with an
   explanatory error, so a public URL is never an open proxy.
3. **Volumes**: attach a volume to the service (any mount path). DAEDALUS uses `RAILWAY_VOLUME_MOUNT_PATH`
   automatically. Without a volume a warning is logged and data is lost on every redeploy.
4. **Networking → Generate Domain** and open the `*.up.railway.app` URL.

Notes: the Dockerfile intentionally has no `VOLUME` instruction (Railway rejects it). A redeploy interrupts running
jobs. Requests to the sources leave from Railway's data-centre IPs, which some social networks block more often.

### VPS behind a reverse proxy

Run Docker Compose as above and put a TLS-terminating proxy in front. With Caddy:

```
daedalus.example.com {
    reverse_proxy 127.0.0.1:8787
}
```

Caddy streams Server-Sent Events out of the box. With Nginx, disable buffering for the API
(`proxy_buffering off;`; DAEDALUS also sends `X-Accel-Buffering: no`) and raise `proxy_read_timeout` above the
longest job you expect.

## 5. Security model

- **Single user / shared password.** There are no accounts or roles. Anyone with the password can read and modify
  every investigation and the settings (including API keys).
- **Basic auth** protects every route except `/healthz`. Wrong passwords are answered after a one-second delay.
  Always serve it over **HTTPS** when it leaves your machine.
- **Railway guard rail**: the app refuses to start on Railway without `DAEDALUS_PASSWORD`.
- **SSRF guard**: transforms that fetch user-supplied URLs (`to_website`, `web_page_scan`, `security_txt`) resolve the
  host first and refuse private, loopback, link-local, reserved and multicast addresses, re-checking every redirect.
  Controlled by *Settings → Block private addresses* (on by default).
- **XSS**: every value coming from sources is escaped before being inserted in the page; only `http(s)` links are
  rendered; external links use `rel="noopener noreferrer nofollow"`. Remote images are only loaded on demand and
  with `referrerpolicy="no-referrer"`.
- **Secrets at rest**: API keys live in `settings.json` in plain text. Protect the data folder (or the volume).
- **Plugins** are arbitrary Python code executed with the app's privileges. Only install plugins you trust.
- Responses carry `X-Content-Type-Options: nosniff` and `Referrer-Policy: no-referrer`.

## 6. Data model

SQLite tables (created by `store.py`):

| Table | Key | Columns |
|---|---|---|
| `cases` | `id` | `name`, `notes`, `layout` (JSON: node positions and layout name), `created`, `updated` |
| `entities` | `(case_id, id)` | `type`, `value`, `props` (JSON), `notes`, `bookmark`, `root`, `created`, `updated` |
| `links` | `(case_id, src, dst, label)` | `transform` (which transform or `manual` created it), `created` |
| `runs` | `id` | `case_id`, `entity_id`, `transform`, `status`, `message`, `found`, `started`, `finished` |

**Entity ids** are `type:value` after normalisation (`domain:example.com`, `email:daedalusintelligence@gmail.com`). Normalisation
lower-cases emails, domains, aliases and hashes, canonicalises IPs and CIDRs, strips phone formatting, and so on;
free-text types (person, organization, location, phrase, account, url) are compared case-insensitively. Adding an
entity that already exists merges its properties instead of duplicating it. A link is unique per
`(source, target, label)`.

**Properties** are free-form JSON. Lists are merged without duplicates, objects are merged key by key, scalars are
overwritten. Keys starting with `_` are reserved for the interface and hidden from the property table:

| Key | Format | Used for |
|---|---|---|
| `_sources` | `["Transform title", …]` | Which transforms produced or enriched the entity. |
| `_links` | `[["label", "https://…"], …]` | External links shown in the inspector. |
| `_dates` | `[["what happened", "YYYY-MM-DD"], …]` | Events shown in the timeline. |
| `_lat`, `_lon` | numbers | Position on the map. |
| `_image` | URL | Avatar/screenshot (loaded on demand). |
| `_unverified` | `[["site", "https://…"], …]` | Sites to check by hand (alias sweep). |
| `_aliases` | `["old value", …]` | Values of entities merged into this one. |

## 7. Transform engine

- **Jobs.** `POST /run` or `/machine` returns a `job_id` immediately; the job runs in the background and emits events
  that the browser reads through Server-Sent Events. Jobs live in memory (the last 30 finished jobs are kept); runs and
  results are persisted as they happen, so nothing is lost if the browser disconnects.
- **Concurrency.** Up to 10 transform runs at once per job; the alias sweep makes up to 25 parallel requests.
  The shared HTTP client follows redirects, uses a 20 s timeout (10 s to connect) and a browser-like User-Agent.
- **Per run.** Each run gets a `Context` bound to one entity and one transform. Required API keys are checked
  first (missing → `skipped`). The run has a timeout (45 s by default, longer for slow sources) and a result limit:
  after `limit` entities, `ctx.add()` returns `None` and the run is reported as truncated.
- **Statuses.** `ok` (entities or properties added), `empty`, `skipped` (raised `Skip`: missing key, rate limit,
  unsupported input), `error` (network error, timeout or exception; full traceback in the server log).
- **Run all** runs every transform whose `default` flag is true and that accepts the entity.
- **Machines.** Stage *n* runs its transforms on the entities produced by stage *n−1* (the seeds for the first stage),
  never running the same transform twice on the same entity. Expansion stops when `machine_max_entities` entities
  have been expanded. The generic *Labyrinth* machine repeats "all default transforms" for 1-4 levels.
- **Cancel.** `POST /api/jobs/{id}/cancel` cancels the asyncio task; results already stored stay.

## 8. HTTP API

Everything the interface does goes through this JSON API, so you can script DAEDALUS. Bodies are JSON unless noted.
With a password set, send HTTP Basic credentials (any user name). Errors return `{"detail": "..."}` with status 400
(bad input), 401 (auth), 404 (unknown case/entity/job), 413 (upload too large) or 422 (schema validation).

### Objects

```jsonc
// entity
{"id": "email:daedalusintelligence@gmail.com", "type": "email", "value": "daedalusintelligence@gmail.com", "label": "daedalusintelligence@gmail.com",
 "props": {"_sources": ["Manual"]}, "notes": "", "bookmark": "", "root": true, "created": 1792757057.3, "updated": 1792757057.3}
// link
{"src": "username:daedalusintelligence", "dst": "email:daedalusintelligence@gmail.com", "label": "public email", "transform": "github_profile"}
// run
{"id": 7, "case_id": 1, "entity_id": "ip:203.0.113.9", "transform": "shodan_internetdb", "status": "ok",
 "message": "2 result(s)", "found": 2, "started": 1792757060.1, "finished": 1792757061.4}
```

### Endpoints

| Method & path | Body / query | Returns |
|---|---|---|
| `GET /healthz` | — | `{"ok": true, "version"}` (no auth) |
| `GET /api/meta` | — | entity types and categories, transforms (with `ready` = keys present), machines, languages, plugins |
| `POST /api/detect` | `{"value"}` | `{"type"}` detected entity type |
| `GET /api/settings` | — | settings, API keys masked (`{"set", "masked", "label", "url"}`) |
| `PUT /api/settings` | any subset of settings, `{"api_keys": {"shodan": "…"}}` (empty string removes a key) | settings |
| `GET /api/cases` | — | `[{"id", "name", "created", "updated", "entities", "links"}]` |
| `POST /api/cases` | `{"name", "notes"?}` | case |
| `GET /api/cases/{id}` | — | `{"case", "entities", "links", "runs"}` |
| `PATCH /api/cases/{id}` | `{"name"?, "notes"?, "layout"?}` | case |
| `DELETE /api/cases/{id}` | — | `{"ok": true}` |
| `POST /api/cases/{id}/entities` | `{"value", "type"?, "props"?, "notes"?, "parent"?, "label"?}` | `{"entity", "created", "link"}`; with `parent`, a manual link parent → entity is created |
| `POST /api/cases/{id}/entities/update` | `{"id", "value"?, "props"?, "replace"?, "notes"?, "bookmark"?}` | `{"entity", "renamed_from", "links"}`; `props` merges, `replace` overwrites (`null` deletes a key), a new `value` renames/merges |
| `POST /api/cases/{id}/entities/delete` | `{"ids": [...]}` | `{"deleted"}` |
| `POST /api/cases/{id}/entities/merge` | `{"keep", "drop": [...]}` | `{"entity", "links"}` |
| `POST /api/cases/{id}/links` | `{"src", "dst", "label"}` | link (`transform: "manual"`) |
| `POST /api/cases/{id}/links/delete` | `{"src", "dst", "label"}` | `{"ok"}` |
| `GET /api/cases/{id}/runs` | `?entity=<id>` optional | `[run]` |
| `POST /api/cases/{id}/run` | `{"entity_ids", "transforms"?, "limit"?}` (`transforms` omitted = all default ones) | `{"job_id"}` |
| `POST /api/cases/{id}/machine` | `{"entity_ids", "machine", "depth"?: 2, "limit"?}` | `{"job_id"}` |
| `GET /api/jobs/{job_id}/events` | — | `text/event-stream` (see below) |
| `POST /api/jobs/{job_id}/cancel` | — | `{"ok"}` |
| `POST /api/cases/{id}/paths` | `{"src", "dst", "k"?: 5 (1-25), "max_len"? (1-30), "directed"?: false}` | `{"paths": [{"nodes", "length", "hops": [{"src", "dst", "labels", "forward"}]}]}` |
| `POST /api/cases/{id}/connect` | `{"ids", "directed"?}` (≤ 25 ids) | `{"nodes", "edges", "unreachable"}` |
| `GET /api/cases/{id}/analysis` | — | `stats`, `degree`, `betweenness`, `pagerank`, `communities`, `component`, `articulation_points`, `bridges`, `hubs`, `similar` |
| `POST /api/cases/{id}/similar` | `{"ids": [id]}` | `{"similar": [{"id", "shared", "jaccard"}]}` |
| `POST /api/cases/{id}/upload` | multipart `file` (image ≤ 40 MB) | `{"entity"}` (image + hash, location, people) |
| `GET /api/cases/{id}/export` | `?format=json\|graphml\|csv\|links-csv` | file download |
| `POST /api/import` | multipart `file` (DAEDALUS JSON) | the new case |

### Live job events

`GET /api/jobs/{job_id}/events` is a Server-Sent Events stream. Each message is `data: <json>`; a `: ping` comment
is sent every 15 s. The stream replays the job from its first event, so reconnecting never misses anything, and it
ends after `done` or `error`.

| `type` | Fields | When |
|---|---|---|
| `plan` | `runs` (transforms) or `machine`, `stages` | Job planned. |
| `stage` | `index`, `runs`, `frontier` | A machine stage starts. |
| `run_start` | `entity_id`, `transform` | A transform starts on an entity. |
| `entity` | `entity`, `created`, `parent`? | An entity was added (`parent` = the entity it hangs from) or its properties changed. |
| `link` | `link` | A new link. |
| `run` | `run` | A transform finished (with status and message). |
| `error` | `message` | The job crashed. |
| `done` | `created`, `seconds`, `cancelled`? | The job ended. |

### Example: script a quick investigation

```bash
API=http://127.0.0.1:8787/api
CASE=$(curl -s -X POST $API/cases -H 'content-type: application/json' -d '{"name":"scripted"}' | jq .id)
ID=$(curl -s -X POST $API/cases/$CASE/entities -H 'content-type: application/json' \
      -d '{"value":"example.com"}' | jq -r .entity.id)
JOB=$(curl -s -X POST $API/cases/$CASE/machine -H 'content-type: application/json' \
      -d "{\"entity_ids\":[\"$ID\"],\"machine\":\"domain_footprint\"}" | jq -r .job_id)
curl -sN $API/jobs/$JOB/events | grep --line-buffered '"type": "done"' | head -1
curl -s "$API/cases/$CASE/export?format=graphml" -o example.graphml
```

Add `-u any:$DAEDALUS_PASSWORD` to every call when a password is set.

## 9. Graph algorithms

All in `graphalgo.py`, without external dependencies, on the multigraph of the investigation (parallel links collapse
into one edge; direction is ignored unless `directed` is requested).

| Feature | Algorithm | Notes |
|---|---|---|
| Ariadne's thread | Yen's *k* shortest loop-free paths over BFS | Paths ordered by hops; optional maximum length and directed mode. |
| Connect selection | Union of pairwise shortest paths | Up to 25 entities. |
| Betweenness | Brandes, normalised to 0-1 | Sampled from 300 sources when the graph has more than 1,500 entities. |
| PageRank | Power iteration, damping 0.85 | Directed, with dangling-node handling. |
| Communities | Louvain modularity optimisation | Deterministic; communities numbered from largest to smallest. |
| Choke points | Tarjan articulation points and bridges | Iterative DFS (no recursion limits). |
| Same identity? | Shared neighbours among same-type entities | At least 2 shared neighbours, not already linked; hubs with more than 150 neighbours are ignored; top 20 by count and Jaccard. |

## 10. Extending DAEDALUS

### Write a transform

```python
from daedalus.transforms import L, Skip, Transform, register


@register
class ToKeybase(Transform):
    name = "my_keybase"                       # unique id (prefix plugin names to avoid clashes)
    title = L("To Keybase proofs", "A pruebas de Keybase")
    description = L("Accounts proven on Keybase.", "Cuentas demostradas en Keybase.")
    category = "social"                       # dns, infrastructure, web, identity, social, search,
                                              # location, crypto, threat or utility
    inputs = ("username",)                    # entity types it accepts
    outputs = ("account",)                    # informative (shown in the reference)
    sources = ("Keybase",)
    keys = ()                                 # required API keys (run is skipped without them)
    optional_keys = ()
    timeout = 45                              # seconds
    default = True                            # include it in "Run all" and the Labyrinth machine

    async def run(self, ctx):
        status, data = await ctx.get_json("https://keybase.io/_/api/1.0/user/lookup.json",
                                          params={"usernames": ctx.value})
        if status != 200:
            raise Skip(f"Keybase HTTP {status}")
        them = (data or {}).get("them") or [None]
        for proof in ((them[0] or {}).get("proofs_summary") or {}).get("all", []):
            if ctx.add("account", proof["service_url"], {"platform": proof["proof_type"]}, label="proves") is None:
                break                          # result limit reached
```

Override `applies(self, entity) -> bool` for finer filters (the wallet transforms only accept BTC/ETH addresses).

### The `Context` API

| Member | Description |
|---|---|
| `ctx.value`, `ctx.props`, `ctx.entity` | The input entity's value, properties and full record. |
| `ctx.http` | Shared `httpx.AsyncClient`. Always `await`; never block the event loop (wrap blocking libraries in `asyncio.to_thread`). |
| `await ctx.get_json(url, **kw)` | GET returning `(status, parsed_json_or_None)` without raising on HTTP errors. |
| `ctx.add(type, value, props=None, label="", parent=None, reverse=False)` | Create or merge an entity and link it from the input entity (or from `parent`); `reverse=True` links it the other way. Returns its id, or `None` when the value is empty or the result limit was reached. |
| `ctx.enrich(props, eid=None)` | Merge properties into the input entity (or `eid`). |
| `ctx.log(message)` | Replace the default status message of the run. |
| `ctx.key(name)` / `ctx.require_key(name)` | Read an API key / read it or skip the run. Add new key names to `API_KEYS` in `config.py`. |
| `await ctx.assert_public(url)` | SSRF guard: raise `Skip` if the URL points to a private address (call it before fetching user-controlled URLs). |
| `ctx.limit`, `ctx.settings`, `ctx.engine` | Result limit, settings and engine (e.g. `ctx.engine.data_dir`). |
| `raise Skip("why")` | End the run with status `skipped` and that message. |

Use the reserved properties of [section 6](#6-data-model) (`_links`, `_dates`, `_lat`/`_lon`, `_image`…) so the
interface shows your data in the inspector, timeline and map.

### Write a machine

```python
from daedalus.transforms import L, Machine, machine

machine(Machine(
    "my_email_pivot",
    L("Email pivot", "Pivote de correo"),
    L("Alias, Gravatar and breaches, then profiles of the aliases.", "Alias, Gravatar y filtraciones, y luego perfiles."),
    ("email",),                               # suggested input types
    [["email_to_alias", "gravatar", "xposedornot"], ["username_profiles", "github_profile"]],
))
```

`chain=False` makes every stage run on all entities seen so far instead of only the last stage's output.

### Plugins

Put `.py` files in `<data dir>/plugins/` and restart. Each file is imported once at start-up (files starting with
`_` are skipped); a plugin that fails to import is logged and ignored. The transforms a plugin adds are listed in
`GET /api/meta` → `plugins`. See [`examples/plugins/email_hashes.py`](../../examples/plugins/email_hashes.py).

### Test it

`tests/conftest.py` provides a `Router` that mocks HTTP by URL regex and a `run_transform()` helper. In a test
module inside `tests/` (with your transform's module imported so it is registered):

```python
from .conftest import run_transform, values

def test_my_keybase(engine_env, router):
    router.add(r"keybase\.io/_/api", json_body={"them": [{"proofs_summary": {"all": [
        {"proof_type": "github", "service_url": "https://github.com/jane"}]}}]})
    graph, run, _ = run_transform(engine_env, router, "my_keybase", "username", "jane")
    assert run["status"] == "ok"
    assert values(graph, "account") == ["https://github.com/jane"]
```

For built-in transforms, also regenerate the reference with `python scripts/gen_docs.py` (a test fails if it is out
of date).

## 11. Frontend

`daedalus/web/index.html` loads the vendored libraries as classic scripts and `js/main.js` as an ES module. There is
no bundler: edit a file and reload.

| Module | Responsibility |
|---|---|
| `main.js` | Bootstrap, investigation management, wiring of every panel, shortcuts, drag & drop. |
| `state.js` | Shared state `S` and `hooks` (refresh callbacks, to avoid import cycles). |
| `graph.js` | Cytoscape setup, styles, node placement, layouts, highlighting, saving positions. |
| `jobs.js` | Starting transforms/machines, consuming the event stream, the Output console. |
| `actions.js`, `ingest.js` | Create/edit/delete/merge/link actions; applying API results to state and canvas. |
| `inspector.js` | Detail and Transforms panels. |
| `menu.js` | Context menus (node, link, canvas, export, investigation). |
| `ariadne.js` | Path finding and analysis panels. |
| `views.js` | Table, map, timeline and notes. |
| `dialogs.js` | New entity, prompt/confirm and the Settings dialog. |
| `i18n.js`, `icons.js`, `util.js` | Translations, entity icons, DOM/HTTP helpers. |

- **Translations**: static text uses `data-i18n`, `data-i18n-ph` (placeholder) and `data-i18n-title` attributes;
  add every new key to both `DICT.en` and `DICT.es` in `i18n.js`. Entity, transform and machine names come from the
  API already bilingual (`L(en, es)` in Python).
- **Debugging**: `window.DAEDALUS` exposes `state` and the `graph` module (`DAEDALUS.graph.cy` is the Cytoscape
  instance).

## 12. Development

```bash
pip install -e ".[dev]"
pytest -q                      # 80+ tests; every HTTP call is mocked, no network needed
ruff check daedalus tests      # lint
python scripts/gen_docs.py     # regenerate docs/*/transforms.md after changing transforms or machines
python scripts/smoke_live.py   # every transform against real public targets (needs internet, a few minutes)
```

CI (GitHub Actions) runs ruff and pytest on Python 3.11, 3.12 and 3.13. Repository layout:

```
daedalus/            application package (backend + web/)
docs/                user guide, technical docs, generated reference, screenshots
examples/            demo investigation and an example plugin
scripts/gen_docs.py  reference generator
scripts/smoke_live.py  live check of every transform against the real sources
tests/               pytest suite
Dockerfile, docker-compose.yml, railway.toml, start.sh, start.bat
```
