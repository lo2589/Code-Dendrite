"""
module_focus_map.py - Top-level capability module map
=====================================================
Builds a high-signal module view from anchors/relations:
  - capability buckets (not folder tree)
  - ranked module importance
  - inter-module edges only

Outputs:
  - .codedendrite/module_focus_map.md
  - .codedendrite/module_focus_map.mmd
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path
from typing import Dict, Tuple


EXCLUDE_PATTERNS = (
    "benchmark/results/",
    ".codedendrite/",
    "__pycache__/",
    "/venv/",
    "/node_modules/",
)


def _normalize(path: str) -> str:
    return path.replace("\\", "/")


def _is_excluded(path: str) -> bool:
    p = _normalize(path).lower()
    return any(token in p for token in EXCLUDE_PATTERNS)


def _bucket(file_path: str) -> str:
    parts = [p for p in _normalize(file_path).split("/") if p]
    if not parts:
        return "root"
    if parts[0] == "tools" and len(parts) > 1:
        return "tools/" + parts[1]
    if parts[0] == "paper_bentch" and len(parts) > 1:
        return "paper_bentch/" + parts[1]
    if parts[0] == "benchmark" and len(parts) > 1:
        return "benchmark/" + parts[1]
    return parts[0]


def _load(root: str) -> Tuple[dict, dict]:
    base = Path(root) / ".codedendrite"
    anchors_path = base / "anchors.json"
    relations_path = base / "relations.json"

    anchors = {}
    if anchors_path.exists():
        anchors = json.loads(anchors_path.read_text(encoding="utf-8"))
    relations = {"edges": []}
    if relations_path.exists():
        relations = json.loads(relations_path.read_text(encoding="utf-8"))
    return anchors, relations


def _build(root: str) -> dict:
    anchors, relations = _load(root)

    sym_to_bucket: Dict[str, str] = {}
    modules = defaultdict(lambda: {"symbols": 0, "files": set(), "in": 0, "out": 0})

    for symbol_id, anchor in anchors.items():
        file_path = str(anchor.get("file", ""))
        if _is_excluded(file_path):
            continue
        bucket = _bucket(file_path)
        sym_to_bucket[symbol_id] = bucket
        modules[bucket]["symbols"] += 1
        modules[bucket]["files"].add(_normalize(file_path))

    edge_counts = defaultdict(int)
    for edge in relations.get("edges", []):
        src = edge.get("from_id")
        dst = edge.get("to_id")
        if src not in sym_to_bucket or dst not in sym_to_bucket:
            continue
        src_mod = sym_to_bucket[src]
        dst_mod = sym_to_bucket[dst]
        modules[src_mod]["out"] += 1
        modules[dst_mod]["in"] += 1
        if src_mod != dst_mod:
            edge_counts[(src_mod, dst_mod)] += 1

    rows = []
    for mod, stat in modules.items():
        score = stat["in"] + stat["out"] + stat["symbols"] * 0.25 + len(stat["files"]) * 0.5
        rows.append(
            {
                "module": mod,
                "score": round(score, 2),
                "in": stat["in"],
                "out": stat["out"],
                "symbols": stat["symbols"],
                "files": len(stat["files"]),
            }
        )
    rows.sort(key=lambda item: (-item["score"], item["module"]))

    return {
        "modules": rows,
        "edges": [
            {"from": src, "to": dst, "count": count}
            for (src, dst), count in sorted(edge_counts.items(), key=lambda x: (-x[1], x[0]))
        ],
    }


def _to_mermaid(data: dict, top_k: int = 8, min_edge: int = 2) -> str:
    top = data["modules"][:top_k]
    keep = {item["module"] for item in top}
    edges = [
        edge
        for edge in data["edges"]
        if edge["from"] in keep and edge["to"] in keep and edge["count"] >= min_edge
    ]

    lines = ["graph TD"]
    for item in top:
        node = item["module"].replace("/", "_").replace("-", "_")
        label = f"{item['module']}\\nscore:{item['score']}\\nin:{item['in']} out:{item['out']}"
        lines.append(f'  {node}["{label}"]')
    for edge in edges:
        src = edge["from"].replace("/", "_").replace("-", "_")
        dst = edge["to"].replace("/", "_").replace("-", "_")
        lines.append(f"  {src} -->|{edge['count']}| {dst}")
    if not edges:
        lines.append("  note[\"No strong cross-module edges in top modules\"]")
    return "\n".join(lines) + "\n"


def _to_markdown(data: dict, mermaid: str, top_k: int = 8) -> str:
    lines = [
        "# Module Focus Map",
        "",
        "## Top Modules (Ranked)",
        "",
        "| rank | module | score | in | out | symbols | files |",
        "|---:|---|---:|---:|---:|---:|---:|",
    ]
    for idx, item in enumerate(data["modules"][:top_k], 1):
        lines.append(
            f"| {idx} | `{item['module']}` | {item['score']} | {item['in']} | {item['out']} | {item['symbols']} | {item['files']} |"
        )
    lines.extend(
        [
            "",
            "## Module Graph",
            "",
            "```mermaid",
            mermaid.rstrip(),
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def generate_module_focus_map(root: str, top_k: int = 8, min_edge: int = 2) -> dict:
    data = _build(root)
    mermaid = _to_mermaid(data, top_k=top_k, min_edge=min_edge)
    markdown = _to_markdown(data, mermaid, top_k=top_k)

    out_dir = Path(root) / ".codedendrite"
    out_dir.mkdir(parents=True, exist_ok=True)
    md_path = out_dir / "module_focus_map.md"
    mmd_path = out_dir / "module_focus_map.mmd"
    md_path.write_text(markdown, encoding="utf-8")
    mmd_path.write_text(mermaid, encoding="utf-8")

    return {
        "md": str(md_path),
        "mmd": str(mmd_path),
        "top_modules": data["modules"][:top_k],
        "edge_count": len(data["edges"]),
    }

