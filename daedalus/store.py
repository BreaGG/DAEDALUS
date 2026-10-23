"""SQLite persistence for cases (graphs), entities, links and transform runs."""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path

from .entities import display_label, entity_id, normalize

SCHEMA = """
CREATE TABLE IF NOT EXISTS cases(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    notes TEXT DEFAULT '',
    layout TEXT DEFAULT '{}',
    created REAL,
    updated REAL
);
CREATE TABLE IF NOT EXISTS entities(
    case_id INTEGER NOT NULL,
    id TEXT NOT NULL,
    type TEXT NOT NULL,
    value TEXT NOT NULL,
    props TEXT DEFAULT '{}',
    notes TEXT DEFAULT '',
    bookmark TEXT DEFAULT '',
    root INTEGER DEFAULT 0,
    created REAL,
    updated REAL,
    PRIMARY KEY(case_id, id)
);
CREATE TABLE IF NOT EXISTS links(
    case_id INTEGER NOT NULL,
    src TEXT NOT NULL,
    dst TEXT NOT NULL,
    label TEXT NOT NULL,
    transform TEXT DEFAULT '',
    created REAL,
    PRIMARY KEY(case_id, src, dst, label)
);
CREATE TABLE IF NOT EXISTS runs(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id INTEGER NOT NULL,
    entity_id TEXT NOT NULL,
    transform TEXT NOT NULL,
    status TEXT,
    message TEXT,
    found INTEGER DEFAULT 0,
    started REAL,
    finished REAL
);
CREATE INDEX IF NOT EXISTS runs_case ON runs(case_id, entity_id);
CREATE INDEX IF NOT EXISTS links_dst ON links(case_id, dst);
"""

BOOKMARKS = ("", "red", "orange", "yellow", "green", "blue", "purple")


def _empty(v) -> bool:
    return v is None or v == "" or v == [] or v == {}


def merge_props(old: dict, new: dict) -> dict:
    """Merge new properties into old ones: lists are unioned, dicts merged, scalars overwritten."""
    out = dict(old)
    for k, v in (new or {}).items():
        if _empty(v):
            continue
        cur = out.get(k)
        if isinstance(v, list) and isinstance(cur, list):
            seen = {json.dumps(x, sort_keys=True, default=str) for x in cur}
            merged = list(cur)
            for x in v:
                s = json.dumps(x, sort_keys=True, default=str)
                if s not in seen:
                    seen.add(s)
                    merged.append(x)
            out[k] = merged
        elif isinstance(v, dict) and isinstance(cur, dict):
            out[k] = {**cur, **v}
        else:
            out[k] = v
    return out


class Store:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.lock = threading.RLock()
        with self.lock:
            self.conn.execute("PRAGMA journal_mode=WAL")
            self.conn.execute("PRAGMA foreign_keys=OFF")
            self.conn.executescript(SCHEMA)
            self.conn.commit()

    def close(self) -> None:
        with self.lock:
            self.conn.close()

    # ------------------------------------------------------------------ cases
    def list_cases(self) -> list[dict]:
        with self.lock:
            rows = self.conn.execute(
                "SELECT c.id, c.name, c.created, c.updated,"
                " (SELECT COUNT(*) FROM entities e WHERE e.case_id = c.id) AS entities,"
                " (SELECT COUNT(*) FROM links l WHERE l.case_id = c.id) AS links"
                " FROM cases c ORDER BY c.updated DESC"
            ).fetchall()
        return [dict(r) for r in rows]

    def create_case(self, name: str, notes: str = "") -> dict:
        now = time.time()
        with self.lock:
            cur = self.conn.execute(
                "INSERT INTO cases(name, notes, created, updated) VALUES(?,?,?,?)",
                ((name or "").strip() or "Untitled", notes or "", now, now),
            )
            self.conn.commit()
        return self.get_case(cur.lastrowid)

    def get_case(self, case_id: int) -> dict | None:
        with self.lock:
            row = self.conn.execute("SELECT * FROM cases WHERE id=?", (case_id,)).fetchone()
        if not row:
            return None
        case = dict(row)
        try:
            case["layout"] = json.loads(case.get("layout") or "{}")
        except ValueError:
            case["layout"] = {}
        return case

    def update_case(self, case_id: int, name: str | None = None, notes: str | None = None,
                    layout: dict | None = None) -> dict | None:
        with self.lock:
            if name is not None and name.strip():
                self.conn.execute("UPDATE cases SET name=? WHERE id=?", (name.strip(), case_id))
            if notes is not None:
                self.conn.execute("UPDATE cases SET notes=? WHERE id=?", (notes, case_id))
            if layout is not None:
                self.conn.execute("UPDATE cases SET layout=? WHERE id=?",
                                  (json.dumps(layout, ensure_ascii=False), case_id))
            self.touch(case_id)
        return self.get_case(case_id)

    def touch(self, case_id: int) -> None:
        with self.lock:
            self.conn.execute("UPDATE cases SET updated=? WHERE id=?", (time.time(), case_id))
            self.conn.commit()

    def delete_case(self, case_id: int) -> None:
        with self.lock:
            for table in ("entities", "links", "runs"):
                self.conn.execute(f"DELETE FROM {table} WHERE case_id=?", (case_id,))
            self.conn.execute("DELETE FROM cases WHERE id=?", (case_id,))
            self.conn.commit()

    # --------------------------------------------------------------- entities
    @staticmethod
    def _entity(row) -> dict:
        props = json.loads(row["props"] or "{}")
        return {
            "id": row["id"],
            "type": row["type"],
            "value": row["value"],
            "label": display_label(row["type"], row["value"], props),
            "props": props,
            "notes": row["notes"] or "",
            "bookmark": row["bookmark"] or "",
            "root": bool(row["root"]),
            "created": row["created"],
            "updated": row["updated"],
        }

    def get_entity(self, case_id: int, eid: str) -> dict | None:
        with self.lock:
            row = self.conn.execute("SELECT * FROM entities WHERE case_id=? AND id=?", (case_id, eid)).fetchone()
        return self._entity(row) if row else None

    def upsert_entity(self, case_id: int, etype: str, value: str, props: dict | None = None,
                      root: bool = False) -> tuple[dict, bool]:
        """Insert an entity or merge props into the existing one. Returns (entity, created)."""
        value = normalize(etype, value)
        eid = entity_id(etype, value)
        props = {k: v for k, v in (props or {}).items() if not _empty(v)}
        now = time.time()
        with self.lock:
            row = self.conn.execute("SELECT props FROM entities WHERE case_id=? AND id=?", (case_id, eid)).fetchone()
            if row:
                merged = merge_props(json.loads(row["props"] or "{}"), props)
                self.conn.execute(
                    "UPDATE entities SET props=?, root=MAX(root, ?), updated=? WHERE case_id=? AND id=?",
                    (json.dumps(merged, ensure_ascii=False, default=str), int(root), now, case_id, eid),
                )
                created = False
            else:
                self.conn.execute(
                    "INSERT INTO entities(case_id, id, type, value, props, root, created, updated)"
                    " VALUES(?,?,?,?,?,?,?,?)",
                    (case_id, eid, etype, value, json.dumps(props, ensure_ascii=False, default=str), int(root), now, now),
                )
                created = True
            self.conn.commit()
        return self.get_entity(case_id, eid), created

    def update_entity(self, case_id: int, eid: str, props: dict | None = None, replace: dict | None = None,
                      notes: str | None = None, bookmark: str | None = None) -> dict | None:
        """props are merged; keys in `replace` are overwritten (a None value deletes the key)."""
        with self.lock:
            row = self.conn.execute("SELECT props FROM entities WHERE case_id=? AND id=?", (case_id, eid)).fetchone()
            if not row:
                return None
            current = json.loads(row["props"] or "{}")
            if props:
                current = merge_props(current, props)
            for k, v in (replace or {}).items():
                if v is None:
                    current.pop(k, None)
                else:
                    current[k] = v
            sets, args = ["props=?", "updated=?"], [json.dumps(current, ensure_ascii=False, default=str), time.time()]
            if notes is not None:
                sets.append("notes=?")
                args.append(notes)
            if bookmark is not None:
                sets.append("bookmark=?")
                args.append(bookmark if bookmark in BOOKMARKS else "")
            self.conn.execute(f"UPDATE entities SET {', '.join(sets)} WHERE case_id=? AND id=?", (*args, case_id, eid))
            self.conn.commit()
        return self.get_entity(case_id, eid)

    def delete_entities(self, case_id: int, ids: list[str]) -> int:
        n = 0
        with self.lock:
            for eid in ids:
                n += self.conn.execute("DELETE FROM entities WHERE case_id=? AND id=?", (case_id, eid)).rowcount
                self.conn.execute("DELETE FROM links WHERE case_id=? AND (src=? OR dst=?)", (case_id, eid, eid))
                self.conn.execute("DELETE FROM runs WHERE case_id=? AND entity_id=?", (case_id, eid))
            self.conn.commit()
        return n

    def merge_entities(self, case_id: int, keep: str, drop: list[str]) -> dict | None:
        """Fold `drop` entities into `keep`: props are merged and links re-pointed."""
        target = self.get_entity(case_id, keep)
        if not target:
            return None
        with self.lock:
            props = target["props"]
            notes = [target["notes"]] if target["notes"] else []
            for eid in drop:
                if eid == keep:
                    continue
                ent = self.get_entity(case_id, eid)
                if not ent:
                    continue
                props = merge_props(props, ent["props"])
                aliases = list(props.get("_aliases") or [])
                if ent["value"] not in aliases and ent["value"] != target["value"]:
                    aliases.append(ent["value"])
                props["_aliases"] = aliases
                if ent["notes"]:
                    notes.append(ent["notes"])
                links = self.conn.execute(
                    "SELECT src, dst, label, transform, created FROM links WHERE case_id=? AND (src=? OR dst=?)",
                    (case_id, eid, eid),
                ).fetchall()
                for ln in links:
                    src = keep if ln["src"] == eid else ln["src"]
                    dst = keep if ln["dst"] == eid else ln["dst"]
                    if src != dst:
                        self.conn.execute(
                            "INSERT OR IGNORE INTO links(case_id, src, dst, label, transform, created) VALUES(?,?,?,?,?,?)",
                            (case_id, src, dst, ln["label"], ln["transform"], ln["created"]),
                        )
                self.conn.execute("UPDATE runs SET entity_id=? WHERE case_id=? AND entity_id=?", (keep, case_id, eid))
                self.conn.execute("DELETE FROM links WHERE case_id=? AND (src=? OR dst=?)", (case_id, eid, eid))
                self.conn.execute("DELETE FROM entities WHERE case_id=? AND id=?", (case_id, eid))
            self.conn.execute(
                "UPDATE entities SET props=?, notes=?, updated=? WHERE case_id=? AND id=?",
                (json.dumps(props, ensure_ascii=False, default=str), "\n\n".join(notes), time.time(), case_id, keep),
            )
            self.conn.commit()
        return self.get_entity(case_id, keep)

    # ------------------------------------------------------------ links / runs
    def add_link(self, case_id: int, src: str, dst: str, label: str, transform: str = "") -> bool:
        if src == dst:
            return False
        with self.lock:
            cur = self.conn.execute(
                "INSERT OR IGNORE INTO links(case_id, src, dst, label, transform, created) VALUES(?,?,?,?,?,?)",
                (case_id, src, dst, label, transform, time.time()),
            )
            self.conn.commit()
        return cur.rowcount > 0

    def delete_link(self, case_id: int, src: str, dst: str, label: str) -> bool:
        with self.lock:
            cur = self.conn.execute("DELETE FROM links WHERE case_id=? AND src=? AND dst=? AND label=?",
                                    (case_id, src, dst, label))
            self.conn.commit()
        return cur.rowcount > 0

    def add_run(self, case_id: int, eid: str, transform: str, status: str, message: str, found: int,
                started: float) -> dict:
        with self.lock:
            cur = self.conn.execute(
                "INSERT INTO runs(case_id, entity_id, transform, status, message, found, started, finished)"
                " VALUES(?,?,?,?,?,?,?,?)",
                (case_id, eid, transform, status, message, found, started, time.time()),
            )
            self.conn.commit()
            row = self.conn.execute("SELECT * FROM runs WHERE id=?", (cur.lastrowid,)).fetchone()
        return dict(row)

    def entities(self, case_id: int) -> list[dict]:
        with self.lock:
            rows = self.conn.execute("SELECT * FROM entities WHERE case_id=? ORDER BY created", (case_id,)).fetchall()
        return [self._entity(r) for r in rows]

    def links(self, case_id: int) -> list[dict]:
        with self.lock:
            rows = self.conn.execute(
                "SELECT src, dst, label, transform FROM links WHERE case_id=? ORDER BY created", (case_id,)
            ).fetchall()
        return [dict(r) for r in rows]

    def runs(self, case_id: int, eid: str | None = None) -> list[dict]:
        with self.lock:
            if eid:
                rows = self.conn.execute("SELECT * FROM runs WHERE case_id=? AND entity_id=? ORDER BY id",
                                         (case_id, eid)).fetchall()
            else:
                rows = self.conn.execute("SELECT * FROM runs WHERE case_id=? ORDER BY id", (case_id,)).fetchall()
        return [dict(r) for r in rows]

    def graph(self, case_id: int) -> dict:
        return {"entities": self.entities(case_id), "links": self.links(case_id), "runs": self.runs(case_id)}
