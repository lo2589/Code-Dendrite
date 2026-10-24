"""Durable Add/Search API for retrieving prior engineering experience.

The storage and ranking interface is independent of any benchmark.  The HTTP
routes implement AML's Coding track contract so a coding agent can consume
the same memories through a standard Add/Search transport.
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Iterator


class InputError(ValueError):
    """A caller supplied a malformed Add or Search request."""


class RequestConflict(ValueError):
    """A request_id was reused with different data in the same user scope."""


def _required_string(body: dict[str, Any], key: str) -> str:
    value = body.get(key)
    if not isinstance(value, str) or not value.strip():
        raise InputError(f"{key} must be a non-empty string")
    return value


def _timestamp(ms: int | None) -> str | None:
    if ms is None:
        return None
    try:
        return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat().replace("+00:00", "Z")
    except (OverflowError, OSError, ValueError) as exc:
        raise InputError("message timestamp is outside the supported range") from exc


def _terms(value: str) -> list[str]:
    # Split code identifiers and paths without losing the original evidence.
    expanded = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", value)
    expanded = re.sub(r"[_./:\\-]+", " ", expanded)
    return re.findall(r"[A-Za-z0-9]+|[\u3400-\u9fff]+", expanded.lower())


class CodingMemoryIndex:
    """Store ordered coding histories and retrieve them within one user scope."""

    def __init__(self, path: str | Path):
        self.path = Path(path).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS writes (
                    user_id TEXT NOT NULL,
                    request_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    payload_hash TEXT NOT NULL,
                    PRIMARY KEY (user_id, request_id)
                );
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    request_id TEXT NOT NULL,
                    session_id TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS memories_user ON memories(user_id);
                CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(
                    memory_id UNINDEXED, terms, tokenize='unicode61'
                );
            """)

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        db = sqlite3.connect(self.path, timeout=30)
        db.execute("PRAGMA busy_timeout=30000")
        try:
            with db:
                yield db
        finally:
            db.close()

    def add(self, body: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(body, dict):
            raise InputError("request body must be an object")
        request_id = _required_string(body, "request_id")
        user_id = _required_string(body, "user_id")
        session_id = _required_string(body, "session_id")
        messages = body.get("messages")
        if not isinstance(messages, list) or not messages:
            raise InputError("messages must be a non-empty array")

        lines: list[str] = []
        first_time: str | None = None
        for i, message in enumerate(messages):
            if not isinstance(message, dict):
                raise InputError(f"messages[{i}] must be an object")
            role = message.get("role")
            content = message.get("content")
            if role not in ("user", "assistant") or not isinstance(content, str) or not content.strip():
                raise InputError(f"messages[{i}] needs role=user|assistant and non-empty string content")
            stamp = message.get("timestamp")
            if stamp is not None and (not isinstance(stamp, int) or isinstance(stamp, bool)):
                raise InputError(f"messages[{i}].timestamp must be Unix milliseconds")
            when = _timestamp(stamp)
            if first_time is None and when is not None:
                first_time = when
            lines.append(f"[{role}{' @ ' + when if when else ''}] {content}")

        payload_hash = hashlib.sha256(json.dumps(body, ensure_ascii=False, sort_keys=True,
                                                 separators=(",", ":")).encode()).hexdigest()
        memory_id = "mem_" + hashlib.sha256(f"{user_id}\0{request_id}".encode()).hexdigest()[:32]
        evidence = "\n".join(lines)
        searchable = " ".join(_terms(evidence))
        created_at = first_time or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        with self._connection() as db:
            db.execute("BEGIN IMMEDIATE")
            previous = db.execute("SELECT payload_hash FROM writes WHERE user_id=? AND request_id=?",
                                  (user_id, request_id)).fetchone()
            if previous is not None:
                if previous[0] != payload_hash:
                    raise RequestConflict("request_id already used with different content")
            else:
                db.execute("INSERT INTO writes VALUES (?, ?, ?, ?)",
                           (user_id, request_id, session_id, payload_hash))
                db.execute("INSERT INTO memories VALUES (?, ?, ?, ?, ?, ?)",
                           (memory_id, user_id, request_id, session_id, evidence, created_at))
                db.execute("INSERT INTO memory_fts (memory_id, terms) VALUES (?, ?)",
                           (memory_id, searchable))
        return {"success": True, "request_id": request_id, "user_id": user_id, "session_id": session_id}

    def search(self, body: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(body, dict):
            raise InputError("request body must be an object")
        query = _required_string(body, "query")
        user_id = _required_string(body, "user_id")
        top_k = body.get("top_k")
        if not isinstance(top_k, int) or isinstance(top_k, bool) or top_k < 1:
            raise InputError("top_k must be a positive integer")
        tokens = list(dict.fromkeys(_terms(query)))
        if not tokens:
            return {"data": []}
        expression = " OR ".join(f'"{token}"' for token in tokens)
        with self._connection() as db:
            rows = db.execute("""
                SELECT m.id, m.content, m.created_at
                FROM memory_fts AS f
                JOIN memories AS m ON m.id = f.memory_id
                WHERE memory_fts MATCH ? AND m.user_id = ?
                ORDER BY bm25(memory_fts), m.created_at DESC, m.id
                LIMIT ?
            """, (expression, user_id, top_k)).fetchall()
        return {"data": [{"id": id_, "content": content, "created_at": created_at}
                         for id_, content, created_at in rows]}


def serve(index: CodingMemoryIndex, key: str, host: str, port: int) -> None:
    """Expose the memory index through AML-compatible HTTP routes."""
    if not key:
        raise ValueError("API key must be non-empty")

    class Handler(BaseHTTPRequestHandler):
        def _json(self, status: int, payload: dict[str, Any]) -> None:
            data = json.dumps(payload, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def _authorized(self) -> bool:
            raw = self.headers.get("X-Api-Key", "")
            if not raw:
                authorization = self.headers.get("Authorization", "")
                match = re.fullmatch(r"(?:Bearer|Token)\s+(.+)", authorization, re.I)
                raw = match.group(1) if match else ""
            return hmac.compare_digest(raw, key)

        def do_GET(self) -> None:  # noqa: N802
            if self.path == "/aml/health":
                self._json(200, {"ok": True})
            else:
                self._json(404, {"detail": "unknown path"})

        def do_POST(self) -> None:  # noqa: N802
            if self.path not in ("/aml/add", "/aml/search"):
                self._json(404, {"detail": "unknown path"})
                return
            if not self._authorized():
                self._json(401, {"detail": "bad or missing API key"})
                return
            try:
                length = int(self.headers.get("Content-Length", "-1"))
                if length < 0:
                    raise InputError("Content-Length is required")
                body = json.loads(self.rfile.read(length))
                result = index.add(body) if self.path == "/aml/add" else index.search(body)
            except RequestConflict as exc:
                self._json(409, {"detail": str(exc)})
            except (InputError, ValueError) as exc:
                self._json(400, {"detail": str(exc)})
            else:
                self._json(200, result)

    httpd = ThreadingHTTPServer((host, port), Handler)
    try:
        httpd.serve_forever()
    finally:
        httpd.server_close()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Serve durable coding-history memory through Add/Search")
    parser.add_argument("--db", type=Path, required=True, help="SQLite database path")
    parser.add_argument("--key-file", type=Path, required=True, help="file containing the API key")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8012)
    args = parser.parse_args(argv)
    serve(CodingMemoryIndex(args.db), args.key_file.read_text().strip(), args.host, args.port)


if __name__ == "__main__":
    main()
