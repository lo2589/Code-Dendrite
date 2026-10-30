"""Read one coding trajectory (an AML Add) as events, and replay the files it touched.

AML sends a solved task as ordered messages: the issue, then the agent's thinking, tool
calls ("[tool_use Read] {json}") and tool results ("[tool_result] ..."). Long results are
split across several user messages; a continuation starts mid-line, so it is glued back
without a newline. Files are replayed in time order: Read records the numbered lines it
saw, Edit applies old_string -> new_string to the current state, Write replaces the file.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any

TOOL_USE = re.compile(r"^\[tool_use (\w+)\]\s*(.*)$", re.S)
NUMBERED = re.compile(r"^\s*(\d+)(?:\t|→)(.*)$")
PREFIXES = ("/testbed/", "/workspace/", "/repo/")


@dataclass
class Event:
    seq: int
    role: str
    kind: str                     # issue | thinking | text | tool_use | tool_result
    text: str
    tool: str = ""
    args: dict = field(default_factory=dict)
    result: str = ""              # filled on tool_use from the following tool_result(s)


@dataclass
class FileState:
    lines: dict[int, str] = field(default_factory=dict)   # line number -> text, as last seen
    edits: list[tuple[int, str, str, int]] = field(default_factory=list)  # (event seq, old, new, line or 0)

    def text(self) -> str:
        return "\n".join(self.lines[k] for k in sorted(self.lines))

    def contiguous(self) -> bool:
        keys = sorted(self.lines)
        return bool(keys) and keys[0] == 1 and keys[-1] == len(keys)


def norm_path(path: str) -> str:
    for p in PREFIXES:
        if path.startswith(p):
            return path[len(p):]
    return path.lstrip("./")


def events(messages: list[dict[str, Any]]) -> list[Event]:
    out: list[Event] = []
    pending: Event | None = None          # the tool_use waiting for its result
    for i, m in enumerate(messages):
        role, text = m.get("role"), str(m.get("content") or "")
        if role == "user" and text.startswith("[tool_result]"):
            body = text[len("[tool_result]"):].lstrip(" ")
            if pending is not None:
                pending.result += body
            out.append(Event(i, role, "tool_result", body))
            continue
        if role == "user" and out and out[-1].kind == "tool_result" and not text.startswith("["):
            out[-1].text += text          # continuation of a split tool result
            if pending is not None:
                pending.result += text
            continue
        pending = None
        hit = TOOL_USE.match(text) if role == "assistant" else None
        if hit:
            try:
                args = json.loads(hit.group(2))
            except json.JSONDecodeError:
                args = {"raw": hit.group(2)}
            pending = Event(i, role, "tool_use", text, tool=hit.group(1), args=args if isinstance(args, dict) else {})
            out.append(pending)
        elif role == "assistant" and text.startswith("[thinking]"):
            out.append(Event(i, role, "thinking", text[len("[thinking]"):].strip()))
        elif role == "user" and not any(e.kind == "issue" for e in out):
            out.append(Event(i, role, "issue", text))
        else:
            out.append(Event(i, role, "text", text))
    return out


def replay(evs: list[Event]) -> dict[str, FileState]:
    files: dict[str, FileState] = {}
    for e in evs:
        if e.kind != "tool_use":
            continue
        path = norm_path(str(e.args.get("file_path") or e.args.get("path") or ""))
        if not path:
            continue
        state = files.setdefault(path, FileState())
        if e.tool == "Read":
            for line in e.result.split("\n"):
                hit = NUMBERED.match(line)
                if hit:
                    state.lines[int(hit.group(1))] = hit.group(2)
        elif e.tool == "Write" and isinstance(e.args.get("content"), str):
            state.lines = dict(enumerate(e.args["content"].split("\n"), 1))
        elif e.tool in ("Edit", "MultiEdit"):
            for old, new in _edit_pairs(e.args):
                state.edits.append((e.seq, old, new, _apply(state, old, new)))
    return files


def _edit_pairs(args: dict) -> list[tuple[str, str]]:
    if isinstance(args.get("edits"), list):
        return [(str(x.get("old_string", "")), str(x.get("new_string", ""))) for x in args["edits"]]
    return [(str(args.get("old_string", "")), str(args.get("new_string", "")))]


def _apply(state: FileState, old: str, new: str) -> int:
    """Apply an edit to a contiguous run of known lines; returns the line it landed on, 0 if unknown."""
    if not old or not state.lines:
        return 0
    keys = sorted(state.lines)
    first = old.split("\n")[0].strip()
    for k in keys:
        if state.lines[k].strip() != first:
            continue
        span = old.count("\n") + 1
        if not all(k + j in state.lines for j in range(span)):
            return 0
        block = "\n".join(state.lines[k + j] for j in range(span))
        if block.strip() != old.strip():
            continue
        tail = {n - span + new.count("\n") + 1: state.lines[n] for n in keys if n >= k + span}
        head = {n: state.lines[n] for n in keys if n < k}
        body = dict(zip(range(k, k + new.count("\n") + 1), new.split("\n")))
        state.lines = {**head, **body, **tail}
        return k
    return 0


def issue_title(evs: list[Event]) -> str:
    issue = next((e.text for e in evs if e.kind == "issue"), "")
    lines = [l.strip("# ").strip() for l in issue.splitlines() if l.strip() and l.strip("# ").strip().lower() != "issue"]
    return (lines[0] if lines else "")[:160]
