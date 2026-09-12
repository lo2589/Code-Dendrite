"""Stateful action ledger for task packets."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


VERSION = "cdd.action_session.v1"


def _session_path(root: str | Path, session_id: str) -> Path:
    digest = hashlib.sha256(session_id.encode("utf-8")).hexdigest()[:20]
    return Path(root) / ".codedendrite" / "sessions" / (digest + ".json")


def _fingerprint(kind: str, target: str) -> str:
    return hashlib.sha256((kind + "\0" + target).encode("utf-8")).hexdigest()


def load_session(root: str | Path, session_id: str, max_actions: int = 12) -> dict:
    path = _session_path(root, session_id)
    if path.is_file():
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("session_id") != session_id:
            raise ValueError("session id hash collision")
        return data
    return {
        "version": VERSION,
        "session_id": session_id,
        "max_actions": max_actions,
        "executed": [],
    }


def record_action(
    root: str | Path,
    session_id: str,
    kind: str,
    target: str,
    *,
    max_actions: int = 12,
) -> dict:
    session = load_session(root, session_id, max_actions=max_actions)
    fingerprint = _fingerprint(kind, target)
    repeated = any(row["fingerprint"] == fingerprint for row in session["executed"])
    if not repeated:
        session["executed"].append({
            "fingerprint": fingerprint,
            "kind": kind,
            "target": target,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        })
        path = _session_path(root, session_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(session, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"recorded": not repeated, "repeated": repeated, "session": session}


def apply_action_gate(
    packet: dict,
    root: str | Path,
    session_id: str,
    *,
    max_actions: int = 12,
) -> dict:
    gated = copy.deepcopy(packet)
    session = load_session(root, session_id, max_actions=max_actions)
    action = gated.get("recommended_action")
    execution = {
        "session_id": session_id,
        "executed_count": len(session["executed"]),
        "max_actions": session.get("max_actions", max_actions),
        "status": "ready",
        "stop_reason": None,
        "action_id": None,
    }
    if not action:
        execution.update(status="stopped", stop_reason="no_recommended_action")
    else:
        fingerprint = _fingerprint(action["kind"], action["target"])
        execution["action_id"] = fingerprint[:20]
        if any(row["fingerprint"] == fingerprint for row in session["executed"]):
            gated["recommended_action"] = None
            execution.update(status="stopped", stop_reason="repeated_action")
        elif len(session["executed"]) >= execution["max_actions"]:
            gated["recommended_action"] = None
            execution.update(status="stopped", stop_reason="action_budget_exhausted")
    gated["execution"] = execution
    return gated


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Manage a CDD action session")
    parser.add_argument("command", choices=("status", "done"))
    parser.add_argument("session_id")
    parser.add_argument("root")
    parser.add_argument("kind", nargs="?")
    parser.add_argument("target", nargs="?")
    parser.add_argument("--max-actions", type=int, default=12)
    args = parser.parse_args(argv)
    if args.command == "done":
        if not args.kind or not args.target:
            parser.error("done requires kind and target")
        result = record_action(
            args.root, args.session_id, args.kind, args.target,
            max_actions=args.max_actions,
        )
    else:
        result = load_session(args.root, args.session_id, max_actions=args.max_actions)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
