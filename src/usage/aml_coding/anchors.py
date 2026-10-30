"""Anchors from one trajectory: file::Class.method with line spans and same-file call edges,
plus which events read, edited, tested or named each anchor.

Only code the trajectory actually saw becomes an anchor; the repository itself is never
cloned. A file read in full is parsed with ast; a file seen only in pieces falls back to
def/class lines and indentation (no call edges).
"""

from __future__ import annotations

import ast
import re
import warnings
from dataclasses import dataclass, field

from .trajectory import Event, FileState, norm_path

DEF = re.compile(r"^(\s*)(?:async\s+)?(def|class)\s+(\w+)")
QUALIFIED = re.compile(r"`([A-Za-z_][\w]*(?:\.[A-Za-z_]\w*)+)`|\b([A-Za-z_]\w*\.[A-Za-z_]\w*)\(")
PYTEST = re.compile(r"([\w/.-]+\.py)::(\w+)(?:::(\w+))?")
MAX_ANCHORS = 2000
MAX_CODE_BYTES = 2_000_000


@dataclass
class Anchor:
    path: str
    qualname: str
    kind: str
    start: int
    end: int
    calls: set[str] = field(default_factory=set)
    links: dict[str, set[int]] = field(default_factory=dict)   # how -> event seqs

    @property
    def key(self) -> str:
        return f"{self.path}::{self.qualname}"

    def link(self, how: str, seq: int) -> None:
        self.links.setdefault(how, set()).add(seq)


def _from_ast(path: str, text: str) -> list[Anchor]:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", SyntaxWarning)    # the repository's own code, not ours
        tree = ast.parse(text)
    out: list[Anchor] = []

    def visit(node, prefix: str) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                name = f"{prefix}.{child.name}" if prefix else child.name
                a = Anchor(path, name, "class" if isinstance(child, ast.ClassDef) else "function",
                           child.lineno, getattr(child, "end_lineno", child.lineno))
                for sub in ast.walk(child):
                    if isinstance(sub, ast.Call):
                        f = sub.func
                        a.calls.add(f.id if isinstance(f, ast.Name) else getattr(f, "attr", ""))
                out.append(a)
                visit(child, name)
    visit(tree, "")
    return out


def _from_lines(path: str, lines: dict[int, str]) -> list[Anchor]:
    out: list[Anchor] = []
    stack: list[tuple[int, str]] = []
    keys = sorted(lines)
    for k in keys:
        m = DEF.match(lines[k])
        if not m:
            continue
        indent = len(m.group(1).expandtabs())
        while stack and stack[-1][0] >= indent:
            stack.pop()
        name = ".".join([n for _, n in stack] + [m.group(3)])
        stack.append((indent, m.group(3)))
        out.append(Anchor(path, name, "class" if m.group(2) == "class" else "function", k, k))
    for i, a in enumerate(out):            # a span ends where the next def at the same or lower indent starts
        indent = len(DEF.match(lines[a.start]).group(1).expandtabs())
        nxt = [b.start for b in out[i + 1:] if len(DEF.match(lines[b.start]).group(1).expandtabs()) <= indent]
        a.end = (nxt[0] - 1) if nxt else keys[-1]
    return out


def extract(files: dict[str, FileState]) -> tuple[list[Anchor], bool]:
    """All anchors of the python files seen, and whether a size cap cut extraction short."""
    anchors, size, capped = [], 0, False
    for path, state in files.items():
        if not path.endswith(".py") or not state.lines:
            continue
        text = state.text()
        size += len(text)
        if size > MAX_CODE_BYTES or len(anchors) >= MAX_ANCHORS:
            capped = True
            break
        try:
            found = _from_ast(path, text) if state.contiguous() else _from_lines(path, state.lines)
        except (SyntaxError, ValueError, RecursionError):
            found = _from_lines(path, state.lines)
        anchors.extend(found[:MAX_ANCHORS - len(anchors)])
    return anchors, capped


def edges(anchors: list[Anchor]) -> list[tuple[str, str]]:
    """Same-file call edges: caller key -> callee key, resolved by short name."""
    by_file: dict[str, dict[str, str]] = {}
    for a in anchors:
        by_file.setdefault(a.path, {})[a.qualname.split(".")[-1]] = a.key
    out = []
    for a in anchors:
        names = by_file.get(a.path, {})
        out.extend((a.key, names[c]) for c in a.calls if c in names and names[c] != a.key)
    return sorted(set(out))


def _containing(anchors: list[Anchor], path: str, line: int) -> Anchor | None:
    hits = [a for a in anchors if a.path == path and a.start <= line <= a.end]
    return min(hits, key=lambda a: a.end - a.start) if hits else None


def attach(evs: list[Event], files: dict[str, FileState], anchors: list[Anchor]) -> None:
    """Hang read / edit / test / mention links from events onto anchors."""
    by_path: dict[str, list[Anchor]] = {}
    for a in anchors:
        by_path.setdefault(a.path, []).append(a)
    by_qual = {a.qualname: a for a in anchors if "." in a.qualname}
    for e in evs:
        if e.kind == "tool_use":
            path = norm_path(str(e.args.get("file_path") or ""))
            if e.tool == "Read" and path in by_path:
                lo = int(e.args.get("offset") or 1)
                hi = lo + int(e.args.get("limit") or 10 ** 9)
                for a in by_path[path]:
                    if a.start < hi and a.end >= lo:
                        a.link("read", e.seq)
            elif e.tool in ("Edit", "MultiEdit") and path in by_path:
                _link_edit(e, files.get(path), by_path[path])
            elif e.tool == "Bash":
                for file, cls, fn in PYTEST.findall(str(e.args.get("command", "")) + e.result):
                    want = f"{cls}.{fn}" if fn else cls
                    for a in by_path.get(norm_path(file), []):
                        if a.qualname == want:
                            a.link("test", e.seq)
        elif e.kind in ("thinking", "text", "issue"):
            for g1, g2 in QUALIFIED.findall(e.text):
                a = by_qual.get(g1 or g2)
                if a is not None:
                    a.link("mention", e.seq)


def _link_edit(e: Event, state: FileState | None, candidates: list[Anchor]) -> None:
    """The replay recorded where each edit landed; anchors are spans of the replayed file."""
    for seq, old, new, line in (state.edits if state else []):
        if seq != e.seq:
            continue
        hit = _containing(candidates, candidates[0].path, line) if line else None
        if hit is None:                                   # fall back to names inside the edited text
            hit = next((a for a in candidates
                        if re.search(rf"\b(def|class)\s+{a.qualname.split('.')[-1]}\b", old + "\n" + new)), None)
        if hit is not None:
            hit.link("edit", e.seq)
