"""
code_map.py - Interactive Code Map (D3.js Treemap)
===================================================
Generates an interactive HTML treemap showing the project structure.
Modules are rectangles sized by symbol count, colored by edge frequency (hotspot).

Features:
  - Treemap layout: modules as rectangles, sized by symbol count
  - Heat coloring: cold (blue) to hot (red) based on total edge count
  - Click module to expand and show internal functions
  - Hover tooltip: module name, symbol count, edge count
  - Zoom/pan support
  - Click function to link to relation graph

Usage:
  python code_map.py <project_root> [--output codemap.html]
"""

import json
import argparse
from pathlib import Path
from typing import Optional
from collections import defaultdict


IGNORE_PATH_PARTS = {"__pycache__"}
IGNORE_PREFIXES = (".tmp_",)

def _should_skip_file(file_path: str) -> bool:
    normalized = file_path.replace("\\", "/")
    parts = [part for part in normalized.split("/") if part]
    if any(part in IGNORE_PATH_PARTS for part in parts):
        return True
    if any(part.startswith(prefix) for part in parts for prefix in IGNORE_PREFIXES):
        return True
    return False

def _build_treemap_data(anchors: dict, relations: dict) -> dict:
    """Build hierarchical treemap data from anchors and relations."""
    # Group anchors by file
    file_symbols = defaultdict(list)
    for aid, anchor in anchors.items():
        file_path = anchor.get("file", "unknown")
        if _should_skip_file(file_path):
            continue
        file_symbols[file_path].append({
            "id": aid,
            "name": anchor.get("symbol", "?"),
            "type": anchor.get("symbol_type", "function"),
            "line": anchor.get("line_start", 0),
        })

    # Compute per-node edge counts
    node_edges = defaultdict(int)
    for e in relations.get("edges", []):
        node_edges[e["from_id"]] += 1
        node_edges[e["to_id"]] += 1

    # Compute per-file edge counts
    file_edges = defaultdict(int)
    for aid in anchors:
        file_path = anchors[aid].get("file", "unknown")
        file_edges[file_path] += node_edges.get(aid, 0)

    # Group files by directory (module)
    module_files = defaultdict(list)
    for file_path, symbols in file_symbols.items():
        parts = file_path.replace("\\", "/").split("/")
        module = parts[0] if len(parts) > 1 else "root"
        module_files[module].append({
            "name": file_path,
            "symbols": symbols,
            "symbol_count": len(symbols),
            "edge_count": file_edges.get(file_path, 0),
        })

    # Build hierarchy: root > module > file > symbol
    children = []
    for module, files in sorted(module_files.items()):
        module_children = []
        total_edges = 0
        total_symbols = 0
        for f in files:
            total_edges += f["edge_count"]
            total_symbols += f["symbol_count"]
            file_children = []
            for sym in f["symbols"]:
                file_children.append({
                    "name": sym["name"],
                    "id": sym["id"],
                    "type": sym["type"],
                    "line": sym["line"],
                    "value": max(1, node_edges.get(sym["id"], 0)),
                    "edges": node_edges.get(sym["id"], 0),
                })
            module_children.append({
                "name": f["name"].replace("\\", "/").split("/")[-1],
                "full_path": f["name"],
                "children": file_children,
                "symbol_count": f["symbol_count"],
                "edge_count": f["edge_count"],
            })
        children.append({
            "name": module,
            "children": module_children,
            "symbol_count": total_symbols,
            "edge_count": total_edges,
        })

    return {
        "name": "project",
        "children": children,
    }
