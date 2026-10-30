"""AML-compatible Add / Search / Health for the Coding track (standard library only).

    python -m usage.aml_coding serve --data DIR --key-file FILE [--port 8014] [--budget-yuan 100]
    python -m usage.aml_coding stats --data DIR
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import re
import shutil
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from . import embed
from .ledger import Ledger
from .search import search
from .store import InputError, RequestConflict, add, init

MIN_FREE_BYTES = 3 * 1024 ** 3


class Unavailable(Exception):
    """503: spending cap reached, disk nearly full, or the embedding provider is down."""


class App:
    def __init__(self, data_dir: str | Path, api_key: str, budget_yuan: float, embedder=None):
        if not api_key:
            raise ValueError("API key must be non-empty")
        self.root = Path(data_dir)
        self.root.mkdir(parents=True, exist_ok=True)
        self.db = self.root / "aml_coding.db"
        init(self.db)
        self.check_key_file = embedder is None
        self.embedder = embedder or embed.Embedder(self.root / "embed_cache.db")
        self.ledger = Ledger(self.root / "calls.db")
        self.key, self.budget = api_key, budget_yuan

    def health(self) -> str | None:
        if self.check_key_file and not embed.ready():
            return "embedding key file missing"
        if shutil.disk_usage(self.root).free < MIN_FREE_BYTES:
            return "disk almost full"
        return None

    def authorized(self, headers) -> bool:
        raw = headers.get("X-Api-Key", "")
        if not raw:
            match = re.fullmatch(r"(?:Bearer|Token)\s+(.+)", headers.get("Authorization", ""), re.I)
            raw = match.group(1) if match else ""
        return hmac.compare_digest(raw.encode(), self.key.encode())

    def add(self, body: dict[str, Any]) -> tuple[dict, dict]:
        if self.ledger.total_cost() >= self.budget:
            raise Unavailable(f"spending cap of {self.budget} yuan reached")
        reason = self.health()
        if reason:
            raise Unavailable(reason)
        stats = add(self.db, body, self.embedder)
        return {"success": True, **{k: body[k] for k in ("request_id", "user_id", "session_id")}}, stats

    def search(self, body: dict[str, Any]) -> tuple[dict, dict]:
        data, stats = search(self.db, body, self.embedder)
        return {"data": data}, stats


def _row(route: str, body: Any, stats: dict) -> dict:
    body = body if isinstance(body, dict) else {}
    user = str(body.get("user_id", ""))
    note = ",".join(k for k in ("new_trajectory", "capped", "degraded") if stats.get(k)) or None
    return {"route": route, "user_hash": hashlib.sha256(user.encode()).hexdigest()[:16] if user else None,
            "request_id": body.get("request_id"),
            "messages": len(body["messages"]) if isinstance(body.get("messages"), list) else None,
            "chunks": stats.get("units"), "duplicate": int(bool(stats.get("duplicate"))),
            "embed_calls": stats.get("calls", 0), "embed_tokens": stats.get("tokens", 0),
            "cost_yuan": stats.get("cost_yuan", 0.0), "error": note}


def make_handler(app: App):
    class Handler(BaseHTTPRequestHandler):
        def _send(self, status: int, payload: dict, headers: dict | None = None) -> int:
            data = json.dumps(payload, ensure_ascii=False).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            for k, v in (headers or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(data)
            return len(data)

        def do_GET(self) -> None:  # noqa: N802
            if self.path != "/aml/health":
                self._send(404, {"detail": "unknown path"})
                return
            reason = app.health()
            self._send(503 if reason else 200, {"ok": False, "detail": reason} if reason else {"ok": True})

        def do_POST(self) -> None:  # noqa: N802
            route = {"/aml/add": "add", "/aml/search": "search"}.get(self.path)
            if route is None:
                self._send(404, {"detail": "unknown path"})
                return
            start, body, stats, raw = time.time(), None, {}, b""
            status, payload, headers = 200, {}, {}
            try:
                if not app.authorized(self.headers):
                    status, payload = 401, {"detail": "bad or missing API key"}
                else:
                    length = int(self.headers.get("Content-Length", "-1"))
                    if length < 0:
                        raise InputError("Content-Length is required")
                    raw = self.rfile.read(length)
                    body = json.loads(raw)
                    if not isinstance(body, dict):
                        raise InputError("request body must be an object")
                    payload, stats = getattr(app, route)(body)
            except RequestConflict as exc:
                status, payload = 409, {"detail": str(exc)}
            except (InputError, ValueError) as exc:
                status, payload = 400, {"detail": str(exc)}
            except embed.RateLimited as exc:
                status, payload, headers = 429, {"detail": str(exc)}, {"Retry-After": str(exc.retry_after)}
            except (embed.EmbedUnavailable, Unavailable) as exc:
                status, payload = 503, {"detail": str(exc)}
            size = self._send(status, payload, headers)
            row = _row(route, body, stats)
            if status != 200:
                row["error"] = payload.get("detail")
            app.ledger.write(**row, status=status, ms=int((time.time() - start) * 1000), bytes_in=len(raw), bytes_out=size)

        def log_message(self, fmt: str, *args) -> None:
            pass

    return Handler


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="usage.aml_coding")
    commands = parser.add_subparsers(dest="command", required=True)
    run = commands.add_parser("serve")
    run.add_argument("--data", type=Path, required=True)
    run.add_argument("--key-file", type=Path, required=True)
    run.add_argument("--host", default="127.0.0.1")
    run.add_argument("--port", type=int, default=8014)
    run.add_argument("--budget-yuan", type=float, default=100.0)
    stats = commands.add_parser("stats")
    stats.add_argument("--data", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "stats":
        print(json.dumps(Ledger(args.data / "calls.db").summary(), ensure_ascii=False, indent=2))
        return
    app = App(args.data, args.key_file.read_text().strip(), args.budget_yuan)
    httpd = ThreadingHTTPServer((args.host, args.port), make_handler(app))
    try:
        httpd.serve_forever()
    finally:
        httpd.server_close()
