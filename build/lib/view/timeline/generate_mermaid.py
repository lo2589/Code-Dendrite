"""
call_timeline.py - Call Chain Timeline (Mermaid sequenceDiagram)
================================================================
Given an entry function, traces its call chain and generates a
Mermaid sequenceDiagram with parameter annotations and error highlighting.

Features:
  - Vertical timeline of function calls from entry point
  - Parameter annotations on arrows (data_in/data_out)
  - Error point highlighting (red note on error_symbol)
  - Depth control (max call depth)
  - Participant grouping by module/file

Usage:
  python call_timeline.py <project_root> <entry_symbol> [--depth 5] [--error symbol] [--output timeline.html]
"""

import json
import argparse
from pathlib import Path
from typing import Optional
from collections import defaultdict

def _build_call_adj(relations: dict):
    """Build adjacency list for call + dispatch edges."""
    adj = defaultdict(list)
    edge_data = {}
    for e in relations.get("edges", []):
        if e.get("edge_type") not in {"call", "dispatch"}:
            continue
        adj[e["from_id"]].append(e["to_id"])
        label = e.get("data_in", "")
        if e.get("edge_type") == "dispatch" and e.get("condition"):
            label = e.get("condition")
        edge_data[(e["from_id"], e["to_id"])] = {
            "data_in": label,
            "data_out": e.get("data_out", ""),
        }
    return adj, edge_data

def _find_entry(entry_symbol: str, anchors: dict, adj: dict) -> str:
    """Find best matching entry node_id."""
    # Exact match
    if entry_symbol in adj or entry_symbol in anchors:
        return entry_symbol

    # Partial match on symbol name
    for nid in list(adj.keys()) + list(anchors.keys()):
        if nid.endswith("::" + entry_symbol):
            return nid
        if nid.endswith("." + entry_symbol):
            return nid
        if entry_symbol in nid:
            return nid
        if "::" in nid:
            tail = nid.split("::")[-1]
            if tail.split(".")[-1] == entry_symbol:
                return nid

    return entry_symbol

def _short_name(node_id: str) -> str:
    """Extract short display name from node_id."""
    if "::" in node_id:
        return node_id.split("::")[-1]
    return node_id

def _safe_alias(node_id: str) -> str:
    """Generate a safe Mermaid participant alias."""
    return node_id.replace("/", "_").replace("\\", "_").replace("::", "__").replace(".", "_").replace("-", "_")

def _get_module(node_id: str) -> str:
    """Extract module from node_id."""
    file_part = node_id.split("::")[0] if "::" in node_id else node_id
    parts = file_part.replace("\\", "/").split("/")
    return parts[0] if len(parts) > 1 else "root"

def _generate_mermaid(calls: list, error_symbol: Optional[str] = None) -> str:
    """Generate Mermaid sequenceDiagram text."""
    if not calls:
        return "sequenceDiagram\n    Note over Entry: No call chain found"

    # Collect participants in order
    participants = []
    seen = set()
    for c in calls:
        for nid in [c["from"], c["to"]]:
            if nid not in seen:
                seen.add(nid)
                participants.append(nid)

    lines = ["sequenceDiagram"]

    # Declare participants with module grouping
    current_module = None
    for nid in participants:
        module = _get_module(nid)
        alias = _safe_alias(nid)
        short = _short_name(nid)
        if module != current_module:
            if current_module is not None:
                lines.append(f"    end")
            lines.append(f"    box {module}")
            current_module = module
        lines.append(f"        participant {alias} as {short}")
    if current_module is not None:
        lines.append(f"    end")

    lines.append("")

    # Draw calls
    for c in calls:
        src = _safe_alias(c["from"])
        tgt = _safe_alias(c["to"])
        label = c["data_in"][:40] if c["data_in"] else ""

        is_error = error_symbol and (
            error_symbol in c["to"] or
            c["to"].endswith("::" + error_symbol)
        )

        if is_error:
            lines.append(f"    {src}->>+{tgt}: {label}")
            lines.append(f"    Note right of {tgt}: ERROR HERE")
            if c["data_out"]:
                lines.append(f"    {tgt}-->>-{src}: {c['data_out'][:40]}")
        else:
            lines.append(f"    {src}->>{tgt}: {label}")
            if c["data_out"]:
                lines.append(f"    {tgt}-->>{src}: {c['data_out'][:40]}")

    return "\n".join(lines)

def _trace_calls(entry: str, adj: dict, edge_data: dict, max_depth: int):
    """BFS trace from entry, return ordered call sequence."""
    calls = []
    visited_edges = set()
    queue = [(entry, 0)]
    visited_nodes = {entry}

    while queue:
        node, depth = queue.pop(0)
        if depth >= max_depth:
            continue

        for target in adj.get(node, []):
            edge_key = (node, target)
            if edge_key in visited_edges:
                continue
            visited_edges.add(edge_key)

            ed = edge_data.get(edge_key, {})
            calls.append({
                "from": node,
                "to": target,
                "depth": depth,
                "data_in": ed.get("data_in", ""),
                "data_out": ed.get("data_out", ""),
            })

            if target not in visited_nodes:
                visited_nodes.add(target)
                queue.append((target, depth + 1))

    return calls
