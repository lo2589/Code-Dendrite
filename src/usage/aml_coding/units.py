"""Retrieval units of one trajectory: one unit per touched anchor, plain chunks for the rest.

An anchor unit carries the symbol, its local graph (calls / called by), the code this task
saw or wrote (signature plus the edited lines), and what the task did to it. Everything
that does not hang on an anchor (the issue, thinking, explanations, command output) is cut
into 100-word chunks with stride 80. A Read of a python file is covered by its anchors and
is not chunked again.
"""

from __future__ import annotations

from dataclasses import dataclass

from .anchors import Anchor
from .trajectory import Event, FileState

UNIT_CHARS = 6000          # about 1,500 tokens
CHUNK_WORDS, CHUNK_STRIDE = 100, 80
NON_PY_READ_WORDS = 2000


@dataclass
class Unit:
    kind: str              # anchor | chunk
    key: str               # file::qualname for anchors, "" for chunks
    path: str
    text: str


def _code(a: Anchor, state: FileState | None) -> str:
    if state is None:
        return ""
    lines = [state.lines[k] for k in range(a.start, a.end + 1) if k in state.lines]
    if len(lines) > 40:
        lines = lines[:25] + [f"    ... ({len(lines) - 35} lines) ..."] + lines[-10:]
    return "\n".join(lines)


def _diffs(a: Anchor, state: FileState | None, seqs: set[int]) -> list[str]:
    if state is None:
        return []
    return [f"- {old.strip()[:400]}\n+ {new.strip()[:400]}" for seq, old, new, _ in state.edits if seq in seqs]


def anchor_unit(a: Anchor, state: FileState | None, callers: list[str], callees: list[str], title: str) -> Unit:
    did = ", ".join(f"{how} x{len(seqs)}" for how, seqs in sorted(a.links.items()))
    parts = [f"{a.key}  ({a.kind}, lines {a.start}-{a.end})", f"task: {title}", f"this task: {did}"]
    if callees:
        parts.append("calls: " + ", ".join(c.split("::")[1] for c in callees[:8]))
    if callers:
        parts.append("called by: " + ", ".join(c.split("::")[1] for c in callers[:8]))
    diffs = _diffs(a, state, a.links.get("edit", set()))
    if diffs:
        parts.append("edit:\n" + "\n".join(diffs))
    parts.append("code:\n" + _code(a, state))
    return Unit("anchor", a.key, a.path, "\n".join(parts)[:UNIT_CHARS])


def windows(text: str) -> list[str]:
    words = text.split()
    if not words:
        return []
    return [" ".join(words[k:k + CHUNK_WORDS])
            for k in range(0, max(1, len(words) - (CHUNK_WORDS - CHUNK_STRIDE)), CHUNK_STRIDE)]


def chunk_units(evs: list[Event]) -> list[Unit]:
    out = []
    for e in evs:
        if e.kind == "tool_result":
            continue                                    # results are read through their tool_use
        if e.kind == "tool_use":
            path = str(e.args.get("file_path") or "")
            if e.tool == "Read" and path.endswith(".py"):
                continue                                # covered by anchors
            head = f"[{e.tool}] " + (str(e.args.get("command") or e.args.get("pattern") or path))[:300]
            body = " ".join(e.result.split()[:NON_PY_READ_WORDS]) if e.tool == "Read" else e.result
            texts = [head + "\n" + w for w in windows(body)] or [head]
        else:
            texts = [f"[{e.kind}] {w}" for w in windows(e.text)]
        out.extend(Unit("chunk", "", "", t) for t in texts)
    return out


def build(evs: list[Event], files: dict[str, FileState], anchors: list[Anchor],
          call_edges: list[tuple[str, str]], title: str) -> list[Unit]:
    callees: dict[str, list[str]] = {}
    callers: dict[str, list[str]] = {}
    for src, dst in call_edges:
        callees.setdefault(src, []).append(dst)
        callers.setdefault(dst, []).append(src)
    units = [anchor_unit(a, files.get(a.path), callers.get(a.key, []), callees.get(a.key, []), title)
             for a in anchors if a.links]
    return units + chunk_units(evs)
