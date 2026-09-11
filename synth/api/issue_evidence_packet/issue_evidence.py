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

from synth.api.issue_evidence_packet.validate_issue_evidence_packet import _candidate_confidence, _match_signal, _repo_files, extract_issue_signals, format_issue_packet_compact, validate_issue_evidence_packet

def generate_issue_evidence_packet(
    issue_text: str,
    root: str = ".",
    anchors: Optional[dict] = None,
) -> dict:
    """Generate a v2 packet from the complete issue text."""
    if anchors is None:
        from index.api.anchors import load_anchors
        anchors = load_anchors(root)

    signals = extract_issue_signals(issue_text)
    files = _repo_files(anchors)
    traceback_ids = [row["id"] for row in signals if row["kind"] == "traceback_frame"]
    deepest_traceback_id = traceback_ids[-1] if traceback_ids else None

    candidate_evidence: dict[str, list[dict]] = defaultdict(list)
    anchor_strength: dict[tuple[str, str], int] = {}
    signal_strengths: dict[str, int] = {}
    strong_file_sets: list[tuple[str, set[str]]] = []
    for signal in signals:
        matches = _match_signal(signal, anchors, files)
        strength = SIGNAL_STRENGTH[signal["kind"]]
        if signal["kind"] == "traceback_frame" and signal["id"] != deepest_traceback_id:
            strength = 1
        matched_files = {row["file"] for row in matches}
        if matched_files:
            signal_strengths[signal["id"]] = strength
        if strength >= 2 and matched_files:
            strong_file_sets.append((signal["id"], matched_files))
        for match in matches:
            evidence = {
                "signal_id": signal["id"],
                "kind": signal["kind"],
                "value": signal["value"],
                "strength": strength,
            }
            candidate_evidence[match["file"]].append(evidence)
            if match["anchor"]:
                key = (match["file"], match["anchor"])
                anchor_strength[key] = max(anchor_strength.get(key, 0), strength)

    selected_files: set[str] = set()
    top_strength = max(
        (signal_strengths[signal_id] for signal_id, _ in strong_file_sets),
        default=0,
    )
    top_file_sets = [
        file_set for signal_id, file_set in strong_file_sets
        if signal_strengths[signal_id] == top_strength
    ]
    if top_file_sets:
        selected_files = set.intersection(*top_file_sets)
        # Lower tiers may narrow a still-ambiguous top tier, but may not overrule
        # a stronger unique path/frame merely because another API is mentioned.
        if selected_files:
            for strength in range(top_strength - 1, 1, -1):
                for signal_id, file_set in strong_file_sets:
                    if signal_strengths[signal_id] != strength:
                        continue
                    narrowed = selected_files & file_set
                    if narrowed:
                        selected_files = narrowed

    all_candidate_files = sorted(candidate_evidence)
    if not strong_file_sets:
        status, confidence, reason = "unresolved", "none", "没有可用于导航的精确证据"
    elif not selected_files:
        status, confidence, reason = "ambiguous", "low", "同级最强证据指向的文件没有交集"
    elif len(selected_files) > 1:
        status, confidence, reason = "ambiguous", "low", "强证据仍对应多个文件"
    else:
        status = "resolved"
        chosen_file = next(iter(selected_files))
        max_strength = max(item["strength"] for item in candidate_evidence[chosen_file])
        confidence = _candidate_confidence(max_strength, True)
        reason = "强证据在唯一文件上收敛"

    candidate_rows = []
    for file_name in sorted(
        all_candidate_files,
        key=lambda name: (0 if name in selected_files else 1, name),
    )[:MAX_CANDIDATES]:
        evidence = sorted(
            candidate_evidence[file_name],
            key=lambda item: (-item["strength"], item["signal_id"]),
        )
        anchor_options = sorted(
            (
                (strength, anchor_id)
                for (candidate_file, anchor_id), strength in anchor_strength.items()
                if candidate_file == file_name
            ),
            key=lambda item: (-item[0], item[1]),
        )
        anchor_id = anchor_options[0][1] if anchor_options else None
        selected = status == "resolved" and file_name in selected_files
        contradictions = [
            signal_id for signal_id, file_set in strong_file_sets
            if file_name not in file_set
        ]
        anchor = anchors.get(anchor_id) if anchor_id else None
        candidate_rows.append({
            "id": "",
            "file": file_name,
            "anchor": anchor_id,
            "symbol": _anchor_attr(anchor, "symbol", "") if anchor else "",
            "line": int(_anchor_attr(anchor, "line_start", 0) or 0) if anchor else None,
            "resolution": "exact" if selected else "possible",
            "confidence": _candidate_confidence(
                max((item["strength"] for item in evidence), default=0), selected,
            ),
            "evidence": evidence,
            "contradictions": contradictions,
        })

    candidates = []
    alternatives = []
    for row in candidate_rows:
        if row["resolution"] == "exact":
            row["id"] = "C{}".format(len(candidates))
            candidates.append(row)
        else:
            row["id"] = "A{}".format(len(alternatives))
            alternatives.append(row)

    matched_signal_ids = {
        item["signal_id"]
        for row in candidate_rows
        for item in row["evidence"]
    }
    boundaries = []
    for signal in signals:
        if signal["id"] in matched_signal_ids and signal["navigation_eligible"]:
            continue
        boundaries.append({
            "id": "B{}".format(len(boundaries)),
            "signal_id": signal["id"],
            "kind": signal["kind"],
            "resolution": (
                "unresolved" if signal["navigation_eligible"] else "unsupported"
            ),
            "reason": (
                "索引中没有精确匹配" if signal["navigation_eligible"]
                else "该信号只提供问题语义，不允许生成导航动作"
            ),
        })

    recommended_action = None
    if status == "resolved":
        selected = candidates[0]
        if selected["anchor"]:
            recommended_action = {
                "kind": "expand_anchor",
                "target": selected["anchor"],
                "argv": ["cdd", "code", selected["anchor"]],
                "because": [item["signal_id"] for item in selected["evidence"] if item["strength"] >= 2],
            }
        else:
            recommended_action = {
                "kind": "inspect_file",
                "target": selected["file"],
                "argv": ["cdd", "file", selected["file"]],
                "because": [item["signal_id"] for item in selected["evidence"] if item["strength"] >= 2],
            }

    first_line = next((line.strip() for line in issue_text.splitlines() if line.strip()), "")
    packet = {
        "version": VERSION,
        "issue": {
            "title": first_line[:200],
            "char_count": len(issue_text),
            "sha256": hashlib.sha256(issue_text.encode("utf-8")).hexdigest(),
            "raw_text_included": False,
        },
        "signals": signals,
        "navigation": {
            "status": status,
            "confidence": confidence,
            "reason": reason,
            "candidate_files": all_candidate_files[:MAX_CANDIDATES],
            "strong_evidence_count": len(strong_file_sets),
            "evidence_boundary": "候选是静态定位证据，不表示缺陷已确认",
        },
        "candidates": candidates,
        "alternatives": alternatives,
        "boundaries": boundaries,
        "recommended_action": recommended_action,
        "action_policy": "最多一个动作；ambiguous/unresolved 时必须为空",
    }
    validate_issue_evidence_packet(packet)
    return packet

def save_issue_evidence_packet(packet: dict, root: str = ".", output: Optional[str] = None) -> str:
    path = Path(output) if output else Path(root) / ".codedendrite" / "issue_evidence_packet.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(packet, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return str(path)

def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Generate a CDD Issue Evidence Packet v2")
    parser.add_argument("target", help="Indexed project root")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--issue-file", help="UTF-8 file containing the complete issue")
    source.add_argument("--issue", help="Complete issue text")
    parser.add_argument("--compact", action="store_true", help="Print compact evidence summary")
    parser.add_argument("--output", help="Custom JSON output path")
    parser.add_argument("--session", help="Apply repeat/budget gate for this task session")
    parser.add_argument("--max-actions", type=int, default=12, help="Session action budget")
    args = parser.parse_args(argv)

    issue_text = (
        Path(args.issue_file).expanduser().read_text(encoding="utf-8")
        if args.issue_file else args.issue
    )
    packet = generate_issue_evidence_packet(issue_text, root=args.target)
    if args.session:
        from synth.api.action_session import apply_action_gate
        packet = apply_action_gate(
            packet, args.target, args.session, max_actions=args.max_actions,
        )
    if args.compact:
        print(format_issue_packet_compact(packet))
    else:
        path = save_issue_evidence_packet(packet, root=args.target, output=args.output)
        print(json.dumps(packet, ensure_ascii=False, indent=2))
        print("Saved: {}".format(path))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
