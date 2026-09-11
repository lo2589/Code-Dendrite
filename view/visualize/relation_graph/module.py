"""
relation_graph.py - Interactive Relation Graph (Cytoscape.js)
=============================================================
Generates a standalone HTML file with an interactive code relation graph.

Features:
  - Nodes colored by module (file path grouping)
  - Edge colors by type: call/inherit/dataflow/impact/dispatch
  - Click node to expand/collapse neighbors
  - Search box with highlight
  - Drag to reposition nodes (cose layout)
  - Hover tooltip: symbol name, file:line, inputs/outputs
  - Legend panel showing edge type colors
  - Filter checkboxes per edge type

Usage:
  python relation_graph.py <project_root> [--focus node_id] [--radius 2] [--output graph.html]
"""

import json
import argparse
import hashlib
from pathlib import Path
from typing import Optional
from collections import defaultdict


EDGE_COLORS = {
    "call": "#58a6ff",
    "inherit": "#3fb950",
    "dataflow": "#bc8cff",
    "impact": "#f85149",
    "dispatch": "#d29922",
}

MODULE_COLORS = [
    "#264653", "#2a9d8f", "#e9c46a", "#f4a261", "#e76f51",
    "#606c38", "#283618", "#dda15e", "#bc6c25", "#023047",
    "#219ebc", "#8ecae6", "#6d6875", "#b5838d", "#ffb4a2",
    "#588157", "#3a5a40", "#a3b18a", "#344e41", "#dad7cd",
]
IGNORE_PATH_PARTS = {"__pycache__"}
IGNORE_PREFIXES = (".tmp_",)

def _should_skip_node(node_id: str) -> bool:
    file_part = node_id.split("::")[0] if "::" in node_id else node_id
    normalized = file_part.replace("\\", "/")
    parts = [part for part in normalized.split("/") if part]
    if any(part in IGNORE_PATH_PARTS for part in parts):
        return True
    if any(part.startswith(prefix) for part in parts for prefix in IGNORE_PREFIXES):
        return True
    return False

def _module_color(module: str) -> str:
    """Deterministic color for a module name."""
    idx = int(hashlib.md5(module.encode()).hexdigest(), 16) % len(MODULE_COLORS)
    return MODULE_COLORS[idx]

def _get_module(node_id: str) -> str:
    """Extract module (directory) from node_id like 'backend/main.py::func'."""
    file_part = node_id.split("::")[0] if "::" in node_id else node_id
    parts = file_part.replace("\\", "/").split("/")
    return parts[0] if len(parts) > 1 else "root"

def _build_cytoscape_elements(edges: list, anchors: dict, node_ids: set = None):
    """Build Cytoscape.js elements JSON with module compound nodes."""
    nodes_set = set()
    cy_edges = []

    for e in edges:
        src = e["from_id"]
        tgt = e["to_id"]
        if _should_skip_node(src) or _should_skip_node(tgt):
            continue
        nodes_set.add(src)
        nodes_set.add(tgt)

    if node_ids:
        nodes_set &= node_ids

    module_nodes = []
    module_seen = set()
    cy_nodes = []
    for nid in sorted(nodes_set):
        module = _get_module(nid)
        if module not in module_seen:
            module_seen.add(module)
            module_nodes.append({
                "data": {
                    "id": module,
                    "label": module,
                    "is_parent": True,
                },
                "classes": "module-container",
            })

        anchor = anchors.get(nid, {})
        symbol = anchor.get("symbol", nid.split("::")[-1] if "::" in nid else nid)
        file_path = anchor.get("file", nid.split("::")[0] if "::" in nid else "")
        line = anchor.get("line_start", "")
        inputs_str = ", ".join(
            f"{i.get('name', '')}:{i.get('type', '')}"
            for i in anchor.get("inputs", [])
        )
        outputs_str = ", ".join(
            f"{o.get('name', '')}:{o.get('type', '')}"
            for o in anchor.get("outputs", [])
        )
        cy_nodes.append({
            "data": {
                "id": nid,
                "parent": module,
                "label": symbol,
                "module": module,
                "file": file_path,
                "line": line,
                "inputs": inputs_str,
                "outputs": outputs_str,
                "color": _module_color(module),
            },
            "classes": "symbol-node",
        })

    for e in edges:
        src = e["from_id"]
        tgt = e["to_id"]
        if src not in nodes_set or tgt not in nodes_set:
            continue
        cy_edges.append({
            "data": {
                "id": f"{src}|{tgt}|{e.get('edge_type', 'call')}|{e.get('condition', '')}",
                "source": src,
                "target": tgt,
                "edge_type": e.get("edge_type", "call"),
                "data_in": e.get("data_in", ""),
                "data_out": e.get("data_out", ""),
                "condition": e.get("condition", ""),
            }
        })

    return module_nodes + cy_nodes + cy_edges

def _filter_by_focus(edges: list, anchors: dict, focus: str, radius: int):
    """BFS from focus node, return edges within radius."""
    adj = defaultdict(set)
    for e in edges:
        adj[e["from_id"]].add(e["to_id"])
        adj[e["to_id"]].add(e["from_id"])

    visited = set()
    frontier = {focus}
    for _ in range(radius):
        next_frontier = set()
        for n in frontier:
            if n not in visited:
                visited.add(n)
                next_frontier |= adj.get(n, set())
        frontier = next_frontier - visited
    visited |= frontier

    filtered_edges = [
        e for e in edges
        if e["from_id"] in visited and e["to_id"] in visited
    ]
    return filtered_edges, visited
