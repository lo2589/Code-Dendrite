"""One database for all users: a trajectory is stored once, each user only keeps references.

AML sends the same ~1,290 trajectories to many user_ids, so Add first fingerprints the
messages; a known trajectory costs one row. A new one is parsed into anchors and units,
its plain chunks are embedded, and everything is written in one transaction.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

import numpy as np

from .anchors import attach, edges, extract
from .trajectory import events, issue_title, replay
from .units import build

SCHEMA = """
CREATE TABLE IF NOT EXISTS trajectories (traj TEXT PRIMARY KEY, created_at INTEGER, title TEXT,
    anchors INTEGER, units INTEGER, capped INTEGER);
CREATE TABLE IF NOT EXISTS requests (user_id TEXT, request_id TEXT, payload_hash TEXT, traj TEXT,
    PRIMARY KEY (user_id, request_id));
CREATE TABLE IF NOT EXISTS units (id INTEGER PRIMARY KEY, traj TEXT, kind TEXT, key TEXT, path TEXT, text TEXT);
CREATE INDEX IF NOT EXISTS units_traj ON units(traj);
CREATE TABLE IF NOT EXISTS vecs (id INTEGER PRIMARY KEY, v BLOB);
CREATE TABLE IF NOT EXISTS symbols (name TEXT, unit INTEGER);
CREATE INDEX IF NOT EXISTS symbols_name ON symbols(name);
CREATE TABLE IF NOT EXISTS links (traj TEXT, key TEXT, how TEXT, n INTEGER);
CREATE INDEX IF NOT EXISTS links_key ON links(key);
CREATE VIRTUAL TABLE IF NOT EXISTS fts USING fts5(text, content='units', content_rowid='id',
    tokenize='porter unicode61');
"""
WRITE_LOCK = threading.Lock()


class InputError(ValueError):
    """Malformed Add or Search request."""


class RequestConflict(ValueError):
    """request_id reused with different content for the same user."""


@contextmanager
def connect(path: Path) -> Iterator[sqlite3.Connection]:
    db = sqlite3.connect(str(path), timeout=30)
    db.execute("PRAGMA busy_timeout=30000")
    try:
        with db:
            yield db
    finally:
        db.close()


def init(path: Path) -> None:
    with connect(path) as db:
        db.execute("PRAGMA journal_mode=WAL")
        db.executescript(SCHEMA)


def required(body: dict[str, Any], key: str) -> str:
    value = body.get(key)
    if not isinstance(value, str) or not value.strip():
        raise InputError(f"{key} must be a non-empty string")
    return value


def _messages(body: dict[str, Any]) -> list[dict]:
    msgs = body.get("messages")
    if not isinstance(msgs, list) or not msgs:
        raise InputError("messages must be a non-empty array")
    for i, m in enumerate(msgs):
        if not isinstance(m, dict) or m.get("role") not in ("user", "assistant") \
                or not isinstance(m.get("content"), str) or not m["content"].strip():
            raise InputError(f"messages[{i}] needs role=user|assistant and non-empty string content")
        ts = m.get("timestamp")
        if ts is not None and (not isinstance(ts, int) or isinstance(ts, bool)):
            raise InputError(f"messages[{i}].timestamp must be Unix milliseconds")
    return msgs


def _hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                     separators=(",", ":")).encode()).hexdigest()


def _names(key: str, path: str) -> set[str]:
    qual = key.split("::", 1)[1] if "::" in key else ""
    parts = qual.split(".")
    return {n.lower() for n in (key, qual, parts[-1], parts[0], path, path.rsplit("/", 1)[-1]) if n}


def add(path: Path, body: dict[str, Any], embedder) -> dict:
    request_id, user_id = required(body, "request_id"), required(body, "user_id")
    required(body, "session_id")
    msgs = _messages(body)
    digest = _hash(body)
    traj = _hash([[m["role"], m["content"]] for m in msgs])
    stats = {"duplicate": False, "new_trajectory": False, "anchors": 0, "units": 0, "capped": False,
             "calls": 0, "tokens": 0, "cost_yuan": 0.0}
    with connect(path) as db:
        prev = db.execute("SELECT payload_hash FROM requests WHERE user_id=? AND request_id=?",
                          (user_id, request_id)).fetchone()
        known = db.execute("SELECT 1 FROM trajectories WHERE traj=?", (traj,)).fetchone()
    if prev:
        if prev[0] != digest:
            raise RequestConflict("request_id already used with different content")
        return {**stats, "duplicate": True}
    parsed = None if known else _parse(msgs)
    if parsed:
        chunks = [u for u in parsed["units"] if u.kind == "chunk"]
        matrix, used = embedder([u.text for u in chunks])
        stats.update(used)
        parsed["vectors"] = dict(zip(map(id, chunks), matrix))
    with WRITE_LOCK, connect(path) as db:
        db.execute("BEGIN IMMEDIATE")
        if parsed and not db.execute("SELECT 1 FROM trajectories WHERE traj=?", (traj,)).fetchone():
            _write(db, traj, msgs, parsed)
            stats.update(new_trajectory=True, anchors=len(parsed["anchors"]),
                         units=len(parsed["units"]), capped=parsed["capped"])
        db.execute("INSERT INTO requests VALUES (?, ?, ?, ?)", (user_id, request_id, digest, traj))
    return stats


def _parse(msgs: list[dict]) -> dict:
    evs = events(msgs)
    files = replay(evs)
    anchors, capped = extract(files)
    attach(evs, files, anchors)
    call_edges = edges(anchors)
    title = issue_title(evs)
    return {"anchors": anchors, "capped": capped, "title": title,
            "units": build(evs, files, anchors, call_edges, title)}


def _write(db: sqlite3.Connection, traj: str, msgs: list[dict], parsed: dict) -> None:
    stamps = [m["timestamp"] for m in msgs if m.get("timestamp") is not None]
    created = min(stamps) if stamps else int(time.time() * 1000)
    db.execute("INSERT INTO trajectories VALUES (?, ?, ?, ?, ?, ?)",
               (traj, created, parsed["title"], len(parsed["anchors"]), len(parsed["units"]), int(parsed["capped"])))
    for u in parsed["units"]:
        uid = db.execute("INSERT INTO units (traj, kind, key, path, text) VALUES (?, ?, ?, ?, ?)",
                         (traj, u.kind, u.key, u.path, u.text)).lastrowid
        db.execute("INSERT INTO fts (rowid, text) VALUES (?, ?)", (uid, u.text))
        if u.kind == "anchor":
            db.executemany("INSERT INTO symbols VALUES (?, ?)", [(n, uid) for n in _names(u.key, u.path)])
        elif id(u) in parsed.get("vectors", {}):
            db.execute("INSERT INTO vecs VALUES (?, ?)", (uid, parsed["vectors"][id(u)].astype(np.float32).tobytes()))
    db.executemany("INSERT INTO links VALUES (?, ?, ?, ?)",
                   [(traj, a.key, how, len(seqs)) for a in parsed["anchors"] for how, seqs in a.links.items()])
