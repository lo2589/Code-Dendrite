"""
module_tree.py - Phase 1 static semantic module tree
====================================================

Phase 1 goals:
  - build .codedendrite/module_tree.json from anchors + relations
  - compute a stable call_structure_hash
  - avoid any LLM dependency
  - provide a light-weight module layer for build_map() section 0
"""

from __future__ import annotations

import ast
import hashlib
import json
from collections import Counter, defaultdict, deque
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

from analyzer.anchors import load_anchors


ENTRY_NOISE_PREFIXES = (
    "_",
    "test_",
    "demo",
    "debug",
    "helper",
    "util",
    "internal",
    "banner",
    "section",
)
STOP_SYMBOL_PREFIXES = (
    "_load",
    "_parse",
    "_read",
    "_write",
    "_format",
    "_build",
    "_get",
    "_set",
)
STOP_DIR_PARTS = {"tests", "utils", "helpers", "examples", "__pycache__"}
EXPAND_EDGE_TYPES = {"call", "dispatch"}
SUMMARY_VERSION = 3

from usage.structure.module_tree.backfill_module_tree_responsibilities import _attach_cross_module_edges, _build_responsibility_hint, _guess_module_name, _merge_named_modules, _merge_raw_modules, _merge_singleton_islands, _rebuild_membership, _refresh_module_names, _symbol_source_dir, _walk_module

def _build_semantic_modules(
    anchors: dict,
    relations: dict,
    scored_entries: list[dict],
) -> Tuple[list[dict], dict[str, str]]:
    adjacency = defaultdict(list)
    for edge in relations.get("edges", []):
        if edge.get("edge_type") not in EXPAND_EDGE_TYPES:
            continue
        adjacency[edge.get("from_id", "")].append(edge.get("to_id", ""))

    raw_modules = []
    for entry in scored_entries[:12]:
        members = _walk_module(entry["symbol_id"], adjacency, anchors)
        if not members:
            continue
        raw_modules.append(
            {
                "entries": [entry],
                "members": members,
            }
        )

    merged = _merge_raw_modules(raw_modules)
    semantic_modules = []
    module_membership: dict[str, str] = {}
    for index, item in enumerate(merged, 1):
        module_id = f"sm_{index:03d}"
        member_symbols = sorted(item["members"])
        entry_functions = [
            {
                "symbol_id": entry["symbol_id"],
                "confidence": entry["confidence"],
                "signal": "+".join(entry["signals"]),
            }
            for entry in sorted(
                item["entries"],
                key=lambda e: (-e["score"], e["symbol_id"]),
            )[:4]
        ]
        primary_entry = entry_functions[0]["symbol_id"] if entry_functions else member_symbols[0]
        semantic_modules.append(
            {
                "id": module_id,
                "name": _guess_module_name(primary_entry, anchors),
                "responsibility": None,
                "responsibility_hint": _build_responsibility_hint(member_symbols),
                "entry_functions": entry_functions,
                "member_symbols": member_symbols,
                "cross_module_edges": [],
                "source_dirs": sorted({_symbol_source_dir(symbol_id) for symbol_id in member_symbols}),
            }
        )
        for symbol_id in member_symbols:
            module_membership[symbol_id] = module_id

    semantic_modules = _merge_named_modules(semantic_modules)
    module_membership = _rebuild_membership(semantic_modules)
    _attach_cross_module_edges(
        semantic_modules=semantic_modules,
        module_membership=module_membership,
        relations=relations,
    )
    semantic_modules = _merge_singleton_islands(semantic_modules)
    module_membership = _rebuild_membership(semantic_modules)
    for module in semantic_modules:
        module["cross_module_edges"] = []
    _attach_cross_module_edges(
        semantic_modules=semantic_modules,
        module_membership=module_membership,
        relations=relations,
    )
    _refresh_module_names(semantic_modules, anchors)

    return semantic_modules, module_membership

def _find_cli_entries(root: Path, anchors: dict) -> set[str]:
    path = root / "api" / "cli.py"
    if not path.exists():
        return set()
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except Exception:
        return set()

    local_functions = {
        node.name for node in tree.body
        if isinstance(node, ast.FunctionDef)
    }
    candidates = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func_name = _call_name(node.func)
            if func_name in {"rebuild", "update", "debug_loop"}:
                candidates.add(func_name)

    result = set()
    for anchor in anchors.values():
        symbol = anchor.symbol or ""
        if anchor.file.replace("\\", "/").endswith("api/cli.py") and symbol in candidates and symbol in local_functions:
            result.add(anchor.id)
    return result

def _call_name(node) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""

def _collect_dispatch_sources(relations: dict) -> dict[str, int]:
    counts = Counter()
    for edge in relations.get("edges", []):
        if edge.get("edge_type") != "dispatch":
            continue
        from_id = edge.get("from_id", "")
        if from_id:
            counts[from_id] += 1
    return dict(counts)

def _collect_dispatch_targets(relations: dict) -> set[str]:
    return {
        edge.get("to_id", "")
        for edge in relations.get("edges", [])
        if edge.get("edge_type") == "dispatch" and edge.get("to_id")
    }

def _compute_call_structure_hash(semantic_modules: list[dict]) -> str:
    payload = []
    for module in semantic_modules:
        payload.append(
            {
                "entries": [entry["symbol_id"] for entry in module["entry_functions"]],
                "members": module["member_symbols"],
                "edges": sorted(
                    (
                        edge["to_module"],
                        edge["edge_type"],
                        edge["count"],
                    )
                    for edge in module["cross_module_edges"]
                ),
            }
        )
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()

def _is_noise_anchor(anchor) -> bool:
    symbol = anchor.symbol or ""
    file_path = anchor.file.replace("\\", "/")
    if symbol.startswith(ENTRY_NOISE_PREFIXES):
        return True
    if any(part in STOP_DIR_PARTS for part in file_path.split("/")):
        return True
    lowered = symbol.lower()
    if any(token in lowered for token in ("helper", "util", "internal", "test", "demo")):
        return True
    return False

def _normalize_symbol_id(symbol_id) -> str:
    if isinstance(symbol_id, dict):
        symbol_id = symbol_id.get("target") or symbol_id.get("id") or symbol_id.get("symbol") or ""
    return str(symbol_id).replace("\\", "/")

def _normalize_anchors(anchors: dict) -> dict:
    normalized = {}
    for anchor in anchors.values():
        anchor.id = _normalize_symbol_id(anchor.id)
        anchor.file = anchor.file.replace("\\", "/")
        anchor.callers = [_normalize_symbol_id(item) for item in anchor.callers]
        anchor.callees = [_normalize_symbol_id(item) for item in anchor.callees]
        normalized[anchor.id] = anchor
    return normalized

def _normalize_relations(relations: dict) -> dict:
    edges = []
    for edge in relations.get("edges", []):
        copy = dict(edge)
        if copy.get("from_id"):
            copy["from_id"] = _normalize_symbol_id(copy["from_id"])
        if copy.get("to_id"):
            copy["to_id"] = _normalize_symbol_id(copy["to_id"])
        edges.append(copy)
    normalized = dict(relations)
    normalized["edges"] = edges
    return normalized

def _normalize_symbol_word(symbol: str) -> str:
    word = symbol.split(".")[-1]
    for prefix in ("run_", "build_", "handle_", "get_", "set_"):
        if word.startswith(prefix):
            word = word[len(prefix):]
    return word.replace("_", " ").strip()

def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _render_project_summary(module_tree: dict, summary_data: dict) -> str:
    lines = [
        f"# {summary_data.get('project_name', 'Project')}",
        "",
        summary_data.get("project_one_line", ""),
        "",
        "## Modules",
        "",
    ]
    modules_by_id = {
        module.get("id"): module
        for module in module_tree.get("semantic_modules", [])
    }
    for module_summary in summary_data.get("modules", []):
        module = modules_by_id.get(module_summary.get("id"), {})
        lines.append(f"### {module_summary.get('name', module_summary.get('id', 'module'))}")
        lines.append(module_summary.get("responsibility", ""))
        lines.append("")
        entry_functions = [
            entry.get("symbol_id", "").split("::")[-1]
            for entry in module.get("entry_functions", [])
            if entry.get("symbol_id")
        ]
        if entry_functions:
            lines.append("Entries: " + " / ".join(entry_functions[:3]))
        member_functions = [
            symbol_id.split("::")[-1]
            for symbol_id in module.get("member_symbols", [])
        ]
        if member_functions:
            lines.append("Functions: " + " -> ".join(member_functions[:4]))
        lines.append("")

    lines.append("## Module Dataflow")
    lines.append("")
    edge_written = False
    for module in module_tree.get("semantic_modules", []):
        for edge in module.get("cross_module_edges", [])[:3]:
            pair_preview = ""
            pairs = edge.get("top_pairs", [])
            if pairs:
                pair_preview = " via {} -> {}".format(
                    pairs[0][0].split("::")[-1],
                    pairs[0][1].split("::")[-1],
                )
            lines.append(
                "{} -> [{}] -> {}{}".format(
                    module.get("name", module.get("id", "?")),
                    edge.get("edge_type", "?"),
                    edge.get("to_module", "?"),
                    pair_preview,
                )
            )
            edge_written = True
    if not edge_written:
        lines.append("No cross-module edges detected.")
    lines.append("")
    lines.append("## Quick Start")
    lines.append("")
    first_entry = None
    for module in module_tree.get("semantic_modules", []):
        entries = module.get("entry_functions", [])
        if entries:
            first_entry = entries[0].get("symbol_id", "")
            break
    lines.append(first_entry or "No entry function detected.")
    lines.append("")
    return "\n".join(lines)
