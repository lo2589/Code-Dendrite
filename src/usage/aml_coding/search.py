"""Search inside the trajectories one user_id references: three routes fused by rank.

Route 1 matches identifiers and paths in the query against anchor names exactly; route 2 is
BM25 over every unit; route 3 is vector similarity over the plain chunks. Reciprocal rank
fusion orders the union. An anchor unit is shown once, with pointers to the other tasks that
touched the same symbol (newest first, no code from them). The reply stops at top_k items
or about 12k tokens, whichever comes first.
"""

from __future__ import annotations

import re
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from . import embed
from .store import InputError, connect, required

ROUTE_LIMIT, RRF_K = 200, 60
SYMBOL_WEIGHT = 3.0
BUDGET_CHARS = 48_000          # about 12k tokens per Search
POINTER_SHARE = 0.2            # cross-task pointers use at most 20% of the budget
VECTOR_SLOTS = threading.BoundedSemaphore(2)
IDENT = re.compile(r"[A-Za-z_][\w]*(?:\.[A-Za-z_]\w*)*|[\w./-]+\.py")
STOP = set("the and for with that this what when where which how does from into not are was were "
           "have has had can could would should will fix bug error test tests file files code".split())


def _top_k(body: dict[str, Any]) -> int:
    top_k = body.get("top_k")
    if not isinstance(top_k, int) or isinstance(top_k, bool) or top_k < 1:
        raise InputError("top_k must be a positive integer")
    return top_k


def _in(trajs: list[str]) -> str:
    return ",".join("?" * len(trajs))


def by_symbol(db, query: str, trajs: list[str]) -> list[int]:
    names = {t.lower() for t in IDENT.findall(query) if len(t) >= 3 and t.lower() not in STOP}
    if not names:
        return []
    rows = db.execute(
        f"SELECT s.unit, COUNT(*) FROM symbols s JOIN units u ON u.id = s.unit "
        f"WHERE s.name IN ({_in(list(names))}) AND u.traj IN ({_in(trajs)}) GROUP BY s.unit "
        f"ORDER BY COUNT(*) DESC LIMIT ?", [*names, *trajs, ROUTE_LIMIT]).fetchall()
    return [r[0] for r in rows]


def by_keyword(db, query: str, trajs: list[str]) -> list[int]:
    terms = [t for t in re.findall(r"[a-z0-9_]+", query.lower()) if len(t) > 2 and t not in STOP]
    if not terms:
        return []
    expression = " OR ".join(f'"{t}"' for t in dict.fromkeys(terms))
    rows = db.execute(
        f"SELECT u.id FROM fts JOIN units u ON u.id = fts.rowid WHERE fts MATCH ? "
        f"AND u.traj IN ({_in(trajs)}) ORDER BY bm25(fts) LIMIT ?", [expression, *trajs, ROUTE_LIMIT]).fetchall()
    return [r[0] for r in rows]


def by_vector(db, query: str, trajs: list[str], embedder) -> tuple[list[int], dict, bool]:
    try:
        qv, stats = embedder([query])
    except (embed.EmbedUnavailable, embed.RateLimited):
        return [], {"calls": 0, "tokens": 0, "cost_yuan": 0.0}, True
    rows = db.execute(f"SELECT u.id, v.v FROM units u JOIN vecs v ON v.id = u.id WHERE u.traj IN ({_in(trajs)})",
                      trajs).fetchall()
    if not rows:
        return [], stats, False
    with VECTOR_SLOTS:
        matrix = np.frombuffer(b"".join(r[1] for r in rows), np.float32).reshape(len(rows), -1)
        sims = matrix @ qv[0]
    order = np.argsort(-sims)[:ROUTE_LIMIT]
    return [rows[i][0] for i in order], stats, False


def fuse(*routes: tuple[list[int], float]) -> list[tuple[int, float]]:
    """Weighted reciprocal rank fusion; an exact symbol hit outweighs a fuzzy one."""
    score: dict[int, float] = {}
    for route, weight in routes:
        for rank, uid in enumerate(route):
            score[uid] = score.get(uid, 0.0) + weight / (RRF_K + rank + 1)
    return sorted(score.items(), key=lambda kv: -kv[1])


def _pointers(db, key: str, traj: str, trajs: list[str]) -> str:
    rows = db.execute(
        f"SELECT t.title, t.created_at, group_concat(l.how) FROM links l JOIN trajectories t ON t.traj = l.traj "
        f"WHERE l.key = ? AND l.traj != ? AND l.traj IN ({_in(trajs)}) GROUP BY l.traj "
        f"ORDER BY t.created_at DESC LIMIT 3", [key, traj, *trajs]).fetchall()
    return "\n".join(f"also touched in task \"{title[:100]}\" ({_iso(ts)[:10]}): {hows}" for title, ts, hows in rows)


def _iso(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def search(path: Path, body: dict[str, Any], embedder) -> tuple[list[dict], dict]:
    query, user_id, top_k = required(body, "query"), required(body, "user_id"), _top_k(body)
    with connect(path) as db:
        trajs = [r[0] for r in db.execute("SELECT DISTINCT traj FROM requests WHERE user_id=?", (user_id,))]
        if not trajs:
            return [], {"calls": 0, "tokens": 0, "cost_yuan": 0.0, "degraded": False}
        vec, stats, degraded = by_vector(db, query, trajs, embedder)
        ranked = fuse((by_symbol(db, query, trajs), SYMBOL_WEIGHT), (by_keyword(db, query, trajs), 1.0), (vec, 1.0))
        out, used, pointer_used, seen_keys = [], 0, 0, set()
        for uid, score in ranked:
            if len(out) >= top_k or used >= BUDGET_CHARS:
                break
            traj, kind, key, text = db.execute("SELECT traj, kind, key, text FROM units WHERE id=?", (uid,)).fetchone()
            if kind == "anchor":
                if key in seen_keys:
                    continue
                seen_keys.add(key)
                extra = _pointers(db, key, traj, trajs)
                if extra and pointer_used + len(extra) <= BUDGET_CHARS * POINTER_SHARE:
                    text, pointer_used = f"{text}\n{extra}", pointer_used + len(extra)
            text = text[:BUDGET_CHARS - used]
            created = db.execute("SELECT created_at FROM trajectories WHERE traj=?", (traj,)).fetchone()[0]
            out.append({"id": f"u{uid}", "content": text, "score": round(score, 5), "created_at": _iso(created)})
            used += len(text)
    return out, {**stats, "degraded": degraded}
