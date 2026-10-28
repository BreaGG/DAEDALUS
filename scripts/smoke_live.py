"""Run every transform once against public, well-known targets and report what each source returned.

    python scripts/smoke_live.py                  # every entity type (a few minutes)
    python scripts/smoke_live.py --types domain,ip

The unit tests mock all HTTP; this is the check against the real sources, worth running before a
release. It uses a throwaway data folder and the API keys of your normal installation, if any.
Exit code 1 if any transform ended in error (a skipped transform only lacks an API key).
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from fastapi.testclient import TestClient  # noqa: E402

from daedalus.api import create_app  # noqa: E402
from daedalus.config import default_data_dir  # noqa: E402
from daedalus.transforms import REGISTRY  # noqa: E402

# public figures, companies and test values only
TARGETS = {
    "domain": "github.com",
    "hostname": "api.github.com",
    "ip": "8.8.8.8",
    "netblock": "8.8.8.0/24",
    "asn": "AS15169",
    "url": "https://www.mozilla.org/",
    "email": "security@mozilla.org",
    "phone": "+1 650-253-0000",
    "username": "torvalds",
    "person": "Linus Torvalds",
    "organization": "Mozilla Foundation",
    "account": "https://github.com/torvalds",
    "location": "48.8584, 2.2945",
    "crypto": "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
    "hash": "44d88612fea8a8f36de82e1278abb02f",
    "vulnerability": "CVE-2021-44228",
    "tracking_code": "G-XXXXXXXXXX",
    "phrase": '"every labyrinth has a way out"',
}
MARK = {"ok": "✓", "empty": "∅", "skipped": "»", "error": "✕"}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--types", help="comma-separated entity types (default: all)")
    args = ap.parse_args()
    types = args.types.split(",") if args.types else list(TARGETS)
    unknown = [t for t in types if t not in TARGETS]
    if unknown:
        ap.error(f"no target for: {', '.join(unknown)} (choose from {', '.join(TARGETS)})")

    tmp = Path(tempfile.mkdtemp(prefix="daedalus-smoke-"))
    keys = default_data_dir() / "settings.json"
    if keys.exists():
        shutil.copy(keys, tmp / "settings.json")
    try:
        with TestClient(create_app(tmp, password="")) as client:
            cid = client.post("/api/cases", json={"name": "Live smoke test"}).json()["id"]
            ents = {}
            for etype in types:
                r = client.post(f"/api/cases/{cid}/entities", json={"value": TARGETS[etype], "type": etype})
                r.raise_for_status()
                ents[r.json()["entity"]["id"]] = etype
            started = time.time()
            job = client.post(f"/api/cases/{cid}/run",
                              json={"entity_ids": list(ents), "transforms": list(REGISTRY), "limit": 12}).json()
            with client.stream("GET", f"/api/jobs/{job['job_id']}/events") as events:
                for line in events.iter_lines():
                    if not line.startswith("data: "):
                        continue
                    ev = json.loads(line[6:])
                    if ev["type"] == "run":
                        run = ev["run"]
                        print(f"  {MARK.get(run['status'], '?')} {ents.get(run['entity_id'], '?'):<14} {run['transform']}",
                              flush=True)
                    if ev["type"] in ("done", "error"):
                        break
            runs = client.get(f"/api/cases/{cid}/runs").json()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print(f"\n{len(runs)} runs in {time.time() - started:.0f} s\n")
    for status in ("error", "empty", "skipped"):
        rows = [r for r in runs if r["status"] == status]
        if rows:
            print(f"{status.upper()} ({len(rows)})")
            for r in rows:
                print(f"  {ents.get(r['entity_id'], '?'):<14} {r['transform']:<28} {r['message'] or ''}"[:160])
            print()
    counts = Counter(r["status"] for r in runs)
    print("  ".join(f"{MARK[s]} {s}: {counts.get(s, 0)}" for s in ("ok", "empty", "skipped", "error")))
    return 1 if counts.get("error") else 0


if __name__ == "__main__":
    sys.exit(main())
