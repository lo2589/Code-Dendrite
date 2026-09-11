"""Build an evidence-preserving task packet from a complete issue description.

The packet deliberately separates extraction, matching, resolution, and action.
No candidate is promoted merely because it has the largest fuzzy score.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Optional

from synth.api.task_context_packet import _anchor_attr, resolve_task_anchor


VERSION = "task_context_packet_v2"
MAX_SIGNALS = 64
MAX_CANDIDATES = 7
CODE_EXTENSIONS = (
    "py", "pyi", "js", "jsx", "ts", "tsx", "java", "go", "rs", "rb",
    "php", "c", "cc", "cpp", "h", "hpp", "cs", "kt", "kts", "scala",
)
GENERIC_IDENTIFIERS = {
    "args", "class", "code", "data", "error", "example", "false", "file",
    "from", "function", "issue", "kwargs", "line", "method", "module",
    "none", "object", "return", "self", "string", "test", "this", "true",
    "value", "when", "with",
}
KEYWORD_STOPWORDS = GENERIC_IDENTIFIERS | {
    "after", "before", "being", "does", "expected", "have", "into", "should",
    "that", "their", "there", "these", "they", "using", "which", "would",
}
SIGNAL_STRENGTH = {
    "anchor_id": 4,
    "traceback_frame": 4,
    "repo_path": 3,
    "api_name": 2,
    "exact_symbol": 2,
    "error_type": 0,
    "keyword": 0,
}

def _anchors_at_line(file_name: str, line: int, anchors: dict) -> list[str]:
    containing = []
    for anchor_id, anchor in anchors.items():
        if _anchor_attr(anchor, "file", "").replace("\\", "/") != file_name:
            continue
        start = int(_anchor_attr(anchor, "line_start", 0) or 0)
        end = int(_anchor_attr(anchor, "line_end", start) or start)
        if start <= line <= end:
            containing.append((max(0, end - start), anchor_id))
    return [anchor_id for _, anchor_id in sorted(containing)]

def _candidate_confidence(max_strength: int, selected: bool) -> str:
    if not selected:
        return "low"
    return "high" if max_strength >= 3 else "medium"

def _normal_path(value: str) -> str:
    return value.strip("`'\"()[]{}.,: ").replace("\\", "/")

def _match_files(path_hint: str, files: list[str]) -> list[str]:
    hint = _normal_path(path_hint).casefold()
    exact = [name for name in files if name.casefold() == hint]
    if exact:
        return exact
    suffix = [
        name for name in files
        if hint.endswith("/" + name.casefold())
        or name.casefold().endswith("/" + hint.lstrip("/"))
    ]
    if suffix:
        return suffix
    basename = Path(hint).name
    return [name for name in files if Path(name).name.casefold() == basename]

def _match_signal(signal: dict, anchors: dict, files: list[str]) -> list[dict]:
    kind = signal["kind"]
    value = signal["value"]
    if kind in {"repo_path", "traceback_frame"}:
        matched_files = _match_files(value, files)
        rows = []
        for file_name in matched_files:
            anchor_ids = (
                _anchors_at_line(file_name, signal["line"], anchors)
                if kind == "traceback_frame" and signal.get("line") else []
            )
            if anchor_ids:
                for anchor_id in anchor_ids:
                    rows.append({"file": file_name, "anchor": anchor_id})
            else:
                rows.append({"file": file_name, "anchor": None})
        return rows

    if kind not in {"anchor_id", "api_name", "exact_symbol"}:
        return []
    matches = resolve_task_anchor(value, anchors)
    if kind == "anchor_id":
        matches = [item for item in matches if item[2] == "exact_id"]
    else:
        matches = [item for item in matches if item[2] in {"exact_id", "symbol_name"}]
    return [
        {
            "file": _anchor_attr(anchor, "file", "").replace("\\", "/"),
            "anchor": anchor_id,
        }
        for anchor_id, anchor, _ in matches
        if _anchor_attr(anchor, "file", "")
    ]

def _repo_files(anchors: dict) -> list[str]:
    return sorted({
        _anchor_attr(anchor, "file", "").replace("\\", "/")
        for anchor in anchors.values()
        if _anchor_attr(anchor, "file", "")
    })

def _signal_key(kind: str, value: str, line: Optional[int]) -> tuple:
    return kind, value.casefold(), line

def extract_issue_signals(issue_text: str) -> list[dict]:
    """Extract typed signals without deciding which one is the defect location."""
    signals: list[dict] = []
    seen = set()

    def add(kind: str, value: str, source: str, line: Optional[int] = None) -> None:
        value = value.strip()
        if not value or len(signals) >= MAX_SIGNALS:
            return
        key = _signal_key(kind, value, line)
        if key in seen:
            return
        seen.add(key)
        row = {
            "id": "S{}".format(len(signals)),
            "kind": kind,
            "value": value,
            "source": source,
            "navigation_eligible": SIGNAL_STRENGTH[kind] > 0,
        }
        if line is not None:
            row["line"] = line
        signals.append(row)

    ext = "|".join(CODE_EXTENSIONS)
    anchor_re = re.compile(
        r"(?P<anchor>(?:[A-Za-z0-9_.-]+[/\\])*[A-Za-z0-9_.-]+\.(?:" + ext
        + r")::[A-Za-z_$][A-Za-z0-9_.$]*(?:\.[A-Za-z_$][A-Za-z0-9_$]*)*)"
    )
    for match in anchor_re.finditer(issue_text):
        add("anchor_id", _normal_path(match.group("anchor")), "explicit_anchor")

    frame_re = re.compile(
        r'File\s+["\'](?P<file>[^"\']+)["\']\s*,\s*line\s+(?P<line>\d+)'
        r'(?:\s*,\s*in\s+(?P<function>[^\s]+))?'
    )
    for match in frame_re.finditer(issue_text):
        add(
            "traceback_frame",
            _normal_path(match.group("file")),
            "traceback",
            int(match.group("line")),
        )
        if match.group("function"):
            add("api_name", match.group("function"), "traceback_function")

    path_re = re.compile(
        r"(?<![\w:])(?P<path>(?:[A-Za-z]:)?(?:[A-Za-z0-9_.-]+[/\\])*"
        r"[A-Za-z0-9_.-]+\.(?:" + ext + r"))"
    )
    for match in path_re.finditer(issue_text):
        add("repo_path", _normal_path(match.group("path")), "explicit_path")

    inline_re = re.compile(r"`([^`\n]{2,180})`")
    for match in inline_re.finditer(issue_text):
        value = match.group(1).strip()
        if anchor_re.fullmatch(value) or path_re.fullmatch(value):
            continue
        if re.fullmatch(r"[A-Za-z_$][A-Za-z0-9_.$]*", value):
            add("exact_symbol", value, "inline_code")

    call_re = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*)\s*\(")
    for match in call_re.finditer(issue_text):
        value = match.group(1)
        if value.casefold() not in GENERIC_IDENTIFIERS:
            add("api_name", value, "call_syntax")

    # Plain snake_case and dotted identifiers are common in issue prose. They are
    # retained only when structurally distinctive; ordinary prose remains weak.
    identifier_re = re.compile(r"\b[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*\b")
    for match in identifier_re.finditer(issue_text):
        value = match.group(0)
        folded = value.casefold()
        distinctive = "_" in value or "." in value or any(c.isupper() for c in value[1:])
        if distinctive and folded not in GENERIC_IDENTIFIERS:
            add("exact_symbol", value, "issue_identifier")

    error_re = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*(?:Error|Exception|Warning))\b")
    for match in error_re.finditer(issue_text):
        add("error_type", match.group(1), "error_name")

    words = re.findall(r"\b[A-Za-z][A-Za-z0-9_-]{4,}\b", issue_text)
    for word in words:
        folded = word.casefold()
        if folded not in KEYWORD_STOPWORDS:
            add("keyword", folded, "issue_text")
        if len([item for item in signals if item["kind"] == "keyword"]) >= 12:
            break

    return signals

def format_issue_packet_compact(packet: dict) -> str:
    nav = packet["navigation"]
    lines = [
        "Issue: {}".format(packet["issue"]["title"] or "(untitled)"),
        "Navigation: {}/{} | {}".format(nav["status"], nav["confidence"], nav["reason"]),
    ]
    for candidate in packet["candidates"]:
        evidence = ", ".join(item["signal_id"] + ":" + item["kind"] for item in candidate["evidence"])
        lines.append("{} {} [{}] evidence={}".format(
            candidate["id"], candidate["anchor"] or candidate["file"],
            candidate["resolution"], evidence,
        ))
    for alternative in packet.get("alternatives", []):
        evidence = ", ".join(
            item["signal_id"] + ":" + item["kind"]
            for item in alternative["evidence"]
        )
        lines.append("{} {} [alternative] evidence={}".format(
            alternative["id"], alternative["anchor"] or alternative["file"], evidence,
        ))
    if packet.get("boundaries"):
        lines.append("Boundaries: {}".format(
            ", ".join(item["signal_id"] + ":" + item["resolution"] for item in packet["boundaries"])
        ))
    action = packet.get("recommended_action")
    lines.append("Action: {}".format(" ".join(action["argv"]) if action else "ABSTAIN"))
    return "\n".join(lines)

def validate_issue_evidence_packet(packet: dict) -> None:
    """Validate the behavioral invariants JSON Schema cannot express alone."""
    if packet.get("version") != VERSION:
        raise ValueError("unsupported packet version")
    navigation = packet.get("navigation") or {}
    status = navigation.get("status")
    if status not in {"resolved", "ambiguous", "unresolved"}:
        raise ValueError("invalid navigation status")

    signal_ids = [item.get("id") for item in packet.get("signals", [])]
    if len(signal_ids) != len(set(signal_ids)):
        raise ValueError("signal ids must be unique")

    candidates = packet.get("candidates") or []
    alternatives = packet.get("alternatives") or []
    if any(item.get("id") != "C{}".format(index) for index, item in enumerate(candidates)):
        raise ValueError("candidate ids must use the C lane")
    if any(item.get("id") != "A{}".format(index) for index, item in enumerate(alternatives)):
        raise ValueError("alternative ids must use the A lane")
    all_rows = candidates + alternatives
    row_ids = [item.get("id") for item in all_rows]
    if len(row_ids) != len(set(row_ids)):
        raise ValueError("candidate/alternative ids must be unique")
    exact = [item for item in candidates if item.get("resolution") == "exact"]
    if any(item.get("resolution") != "exact" for item in candidates):
        raise ValueError("candidate lane accepts exact rows only")
    if any(item.get("resolution") == "exact" for item in alternatives):
        raise ValueError("alternative lane cannot contain exact rows")
    action = packet.get("recommended_action")
    execution = packet.get("execution") or {}
    stopped_by_session = execution.get("status") == "stopped"
    if status == "resolved":
        if len(exact) != 1 or (not action and not stopped_by_session):
            raise ValueError("resolved navigation requires one exact candidate and an action or session stop")
    elif exact or action is not None:
        raise ValueError("ambiguous/unresolved navigation must abstain")

    known_signals = set(signal_ids)
    for candidate in all_rows:
        referenced = {
            item.get("signal_id") for item in candidate.get("evidence", [])
        } | set(candidate.get("contradictions", []))
        if not referenced <= known_signals:
            raise ValueError("candidate references an unknown signal")

    boundary_ids = [item.get("id") for item in packet.get("boundaries", [])]
    if any(
        item.get("id") != "B{}".format(index)
        for index, item in enumerate(packet.get("boundaries", []))
    ):
        raise ValueError("boundary ids must use the B lane")
    if len(boundary_ids) != len(set(boundary_ids)):
        raise ValueError("boundary ids must be unique")
    if any(item.get("signal_id") not in known_signals for item in packet.get("boundaries", [])):
        raise ValueError("boundary references an unknown signal")
    if action:
        if not set(action.get("because", [])) <= known_signals:
            raise ValueError("action references an unknown signal")
        expected_argv = [
            "cdd",
            "code" if action.get("kind") == "expand_anchor" else "file",
            action.get("target"),
        ]
        if action.get("argv") != expected_argv:
            raise ValueError("action argv does not match its structured target")
