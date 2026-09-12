"""Language-neutral conversion from analyzer output to canonical anchor records."""
from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from scanner.language.registry import create_analyzer, language_for_path, supported_extensions


@dataclass
class ParsedAnchor:
    id: str
    symbol: str
    file: str
    line_start: int
    line_end: int
    language: str
    symbol_type: str
    hash: str = ""
    signature: str = ""
    parent_anchor: str | None = None
    imports: list[str] = field(default_factory=list)
    callees: list[str] = field(default_factory=list)
    call_sites: list[dict] = field(default_factory=list)



def _read_lines(path) -> list:
    """The file's lines, or nothing if it cannot be read as text."""
    try:
        with open(path, "r", encoding="utf8", errors="ignore") as handle:
            return handle.read().splitlines()
    except OSError:
        return []


def _body_digest(lines: list, start: int, end: int) -> str:
    """Hash the lines a symbol actually occupies.

    Empty when the range is unusable, so the caller can fall back rather than
    hand out a fingerprint of nothing — every symbol in a file sharing one digest
    would be worse than the scheme this replaces.
    """
    if not lines or start < 1 or end < start or start > len(lines):
        return ""
    body = "\n".join(lines[start - 1:min(end, len(lines))])
    if not body.strip():
        return ""
    from scanner.hashing.ast_hash import body_hash
    return body_hash(body)

def _relative(root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve())).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def _component_script(source: str) -> tuple[str, int]:
    match = re.search(r"<script(?:\s[^>]*)?>(.*?)</script>", source, re.I | re.S)
    if not match:
        return "", 1
    return match.group(1), source.count("\n", 0, match.start(1)) + 1


def _module_for(analyzer, spec, path: Path):
    if spec.analyzer != "component":
        return analyzer.analyze_file(str(path)), 0
    source = path.read_text(encoding="utf-8", errors="replace")
    script, line = _component_script(source)
    if not script:
        return analyzer.analyze_file(str(path)), 0
    from scanner.language.base import ModuleInfo
    module = ModuleInfo(path.name, str(path), 1)
    module.imports = analyzer._extract_imports(script)
    module.classes = analyzer._extract_classes(script)
    module.functions = analyzer._extract_functions(script, str(path))
    return module, line - 1


def _class_name(item) -> str:
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        return str(item.get("name") or "")
    return str(getattr(item, "name", "") or "")


def parse_paths(root: str | Path, paths: Iterable[str | Path], *, include_python: bool = False):
    root_path = Path(root)
    parsed: dict[str, ParsedAnchor] = {}
    failures: list[str] = []
    completed: set[str] = set()
    for raw_path in paths:
        path = Path(raw_path)
        spec = language_for_path(path)
        rel = _relative(root_path, path)
        if spec is None or not spec.executable or (spec.name == "python" and not include_python):
            completed.add(rel)
            continue
        try:
            analyzer = create_analyzer(root_path, path)
            module, line_offset = _module_for(analyzer, spec, path)
            source_lines = _read_lines(path)
            imports = [str(item) for item in (getattr(module, "imports", []) or [])]
            class_items = getattr(module, "class_infos", None) or getattr(module, "classes", []) or []
            for item in class_items:
                name = _class_name(item)
                if not name:
                    continue
                local_start = int(getattr(item, "line_number", 0) or (item.get("start_line", 1) if isinstance(item, dict) else 1))
                local_end = int(getattr(item, "line_end", 0) or (item.get("end_line", local_start) if isinstance(item, dict) else local_start))
                start = local_start + line_offset
                end = local_end + line_offset
                anchor_id = f"{rel}::{name}"
                parsed.setdefault(anchor_id, ParsedAnchor(
                    id=anchor_id, symbol=name, file=rel,
                    line_start=start, line_end=max(start, end),
                    language=spec.name, symbol_type="class", imports=imports,
                ))
            for func in getattr(module, "functions", []) or []:
                name = str(getattr(func, "name", "") or "")
                if not name:
                    continue
                owner = str(getattr(func, "class_name", "") or "")
                lexical_parent = str(getattr(func, "parent_function", "") or "")
                qualified = f"{owner}.{name}" if owner else f"{lexical_parent}.{name}" if lexical_parent else name
                anchor_id = f"{rel}::{qualified}"
                start = int(getattr(func, "line_number", 1) or 1) + line_offset
                end = int(getattr(func, "line_end", 0) or start) + (line_offset if getattr(func, "line_end", 0) else 0)
                calls = list(getattr(func, "calls", []) or [])
                sites = [dict(site) for site in (getattr(func, "call_sites", []) or [])]
                if not sites:
                    sites = [{
                        "target": str(call), "raw_target": str(call),
                        "line": start, "column": 0, "seq": seq,
                        "conds": ["nocond"], "call_kind": "name",
                        "resolution": "unresolved", "evidence": "analyzer-call",
                    } for seq, call in enumerate(calls)]
                for site in sites:
                    site["line"] = int(site.get("line", start) or start) + line_offset
                    site.setdefault("raw_target", site.get("target", ""))
                    site.setdefault("resolution", "unresolved")
                    site.setdefault("evidence", "source-call")
                signature = str(getattr(func, "signature", "") or "")
                # A fingerprint of the code, not of where it sits. The old one was
                # sha1(path:name:start:end) — no source in it at all, so a blank
                # line above said "changed" and a rewritten body that kept its
                # line count said "unchanged". Both answers were backwards.
                digest = _body_digest(source_lines, start, end)
                if not digest:
                    digest = hashlib.sha1(
                        f"{rel}:{qualified}:{start}:{end}".encode()).hexdigest()[:16]
                parsed[anchor_id] = ParsedAnchor(
                    id=anchor_id, symbol=qualified, file=rel,
                    line_start=start, line_end=max(start, end), language=spec.name,
                    symbol_type="method" if owner else "function", hash=digest,
                    signature=signature, parent_anchor=f"{rel}::{owner}" if owner else None,
                    imports=imports, callees=[str(call) for call in calls], call_sites=sites,
                )
                if lexical_parent and not owner:
                    parsed[anchor_id].parent_anchor = f"{rel}::{lexical_parent}"
            completed.add(rel)
        except Exception as exc:
            failures.append(f"{rel}: {type(exc).__name__}: {exc}")
    return parsed, failures, completed


def walk_source_paths(root: str | Path, ignore=None, exclude_dirs=()) -> list[Path]:
    root_path = Path(root)
    extensions = supported_extensions(executable_only=True)
    excluded = set(exclude_dirs or ())
    result = []
    for dirpath, dirnames, filenames in os.walk(root_path):
        directory = Path(dirpath)
        dirnames[:] = [
            name for name in dirnames
            if name not in excluded
            and (ignore is None or ignore.should_scan(directory / name / "_source"))
        ]
        for filename in filenames:
            path = directory / filename
            if path.suffix.lower() not in extensions:
                continue
            if ignore is not None and not ignore.should_scan(path):
                continue
            result.append(path)
    return result
