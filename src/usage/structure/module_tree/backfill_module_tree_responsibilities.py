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

__all__ = [
    "generate_module_tree",
    "load_module_tree",
    "get_module",
    "find_module_for_symbol",
    "query_modules",
    "generate_module_summary",
    "load_summary_cache",
]

def _attach_cross_module_edges(
    semantic_modules: list[dict],
    module_membership: dict[str, str],
    relations: dict,
) -> None:
    module_index = {module["id"]: module for module in semantic_modules}
    grouped: dict[tuple[str, str, str], list[tuple[str, str]]] = defaultdict(list)
    for edge in relations.get("edges", []):
        edge_type = edge.get("edge_type")
        if edge_type not in EXPAND_EDGE_TYPES:
            continue
        from_id = edge.get("from_id", "")
        to_id = edge.get("to_id", "")
        from_module = module_membership.get(from_id)
        to_module = module_membership.get(to_id)
        if not from_module or not to_module or from_module == to_module:
            continue
        grouped[(from_module, to_module, edge_type)].append((from_id, to_id))

    for (from_module, to_module, edge_type), pairs in grouped.items():
        module_index[from_module]["cross_module_edges"].append(
            {
                "to_module": to_module,
                "edge_type": edge_type,
                "count": len(pairs),
                "top_pairs": [list(pair) for pair in pairs[:5]],
            }
        )

def _backfill_module_tree_responsibilities(module_tree: dict, summary_data: dict, output_path: Path) -> None:
    by_id = {
        module.get("id"): module.get("responsibility")
        for module in summary_data.get("modules", [])
    }
    for module in module_tree.get("semantic_modules", []):
        if module.get("id") in by_id:
            module["responsibility"] = by_id[module["id"]]
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(module_tree, f, ensure_ascii=False, indent=2)

def _build_responsibility_hint(member_symbols: list[str]) -> str:
    names = [symbol_id.split("::")[-1].split(".")[-1] for symbol_id in member_symbols[:4]]
    return " -> ".join(names)[:120]

def _camel_to_snake(name: str) -> str:
    out = []
    for index, ch in enumerate(name):
        if ch.isupper() and index > 0 and (not name[index - 1].isupper()):
            out.append("_")
        out.append(ch.lower())
    return "".join(out)

def _guess_module_name(primary_entry: str, anchors: dict) -> str:
    anchor = anchors.get(primary_entry)
    if not anchor:
        return primary_entry.split("::")[-1][:24]
    raw_symbol = anchor.symbol
    parts = raw_symbol.split(".")
    if parts and parts[-1] == "handle_request":
        return "request_router"
    if len(parts) >= 2 and parts[-1] in {"execute", "__init__", "init", "observe", "run"}:
        symbol = parts[-2]
        symbol = symbol.replace("Tool", "").replace("API", "_api")
    else:
        symbol = parts[-1]
    symbol = symbol.replace("run_", "").replace("build_", "")
    symbol = _camel_to_snake(symbol)
    parts = [part for part in symbol.split("_") if part and part not in {"handle", "main", "tool"}]
    if not parts:
        parts = [symbol]
    return "_".join(parts[:3])[:24]

def _should_stop_at_symbol(symbol_id: str, anchors: dict) -> bool:
    anchor = anchors.get(symbol_id)
    if not anchor:
        return True
    symbol = anchor.symbol.split(".")[-1]
    if symbol.startswith(STOP_SYMBOL_PREFIXES):
        return True
    file_path = anchor.file.replace("\\", "/")
    if any(part in STOP_DIR_PARTS for part in file_path.split("/")):
        return True
    return False

def _walk_module(start: str, adjacency: dict, anchors: dict) -> set[str]:
    visited: set[str] = set()
    queue = deque([(start, 0)])
    while queue:
        current, depth = queue.popleft()
        if not current or current in visited:
            continue
        visited.add(current)
        if depth >= 3:
            continue
        for nxt in adjacency.get(current, []):
            if not nxt or nxt in visited:
                continue
            if _should_stop_at_symbol(nxt, anchors):
                visited.add(nxt)
                continue
            queue.append((nxt, depth + 1))
    return visited

def _jaccard(left: Iterable[str], right: Iterable[str]) -> float:
    left_set = set(left)
    right_set = set(right)
    if not left_set and not right_set:
        return 1.0
    if not left_set or not right_set:
        return 0.0
    return len(left_set & right_set) / len(left_set | right_set)

def _merge_raw_modules(raw_modules: list[dict]) -> list[dict]:
    merged: list[dict] = []
    for item in raw_modules:
        placed = False
        for existing in merged:
            if item["members"].issubset(existing["members"]) or existing["members"].issubset(item["members"]):
                existing["members"].update(item["members"])
                by_symbol = {entry["symbol_id"]: entry for entry in existing["entries"]}
                for entry in item["entries"]:
                    old = by_symbol.get(entry["symbol_id"])
                    if old is None or entry["score"] > old["score"]:
                        by_symbol[entry["symbol_id"]] = entry
                existing["entries"] = list(by_symbol.values())
                placed = True
                break
            overlap = _jaccard(item["members"], existing["members"])
            if overlap >= 0.4:
                existing["members"].update(item["members"])
                by_symbol = {entry["symbol_id"]: entry for entry in existing["entries"]}
                for entry in item["entries"]:
                    old = by_symbol.get(entry["symbol_id"])
                    if old is None or entry["score"] > old["score"]:
                        by_symbol[entry["symbol_id"]] = entry
                existing["entries"] = list(by_symbol.values())
                placed = True
                break
        if not placed:
            merged.append(
                {
                    "entries": list(item["entries"]),
                    "members": set(item["members"]),
                }
            )
    return merged

def _merge_entry_functions(left: list[dict], right: list[dict]) -> list[dict]:
    by_id = {item.get("symbol_id"): dict(item) for item in left if item.get("symbol_id")}
    for item in right:
        symbol_id = item.get("symbol_id")
        if not symbol_id:
            continue
        old = by_id.get(symbol_id)
        if old is None:
            by_id[symbol_id] = dict(item)
            continue
        rank = {"high": 3, "medium": 2, "low": 1}
        if rank.get(item.get("confidence", "low"), 1) > rank.get(old.get("confidence", "low"), 1):
            by_id[symbol_id] = dict(item)
    values = list(by_id.values())
    values.sort(key=lambda item: ({"high": 0, "medium": 1, "low": 2}.get(item.get("confidence", "low"), 3), item.get("symbol_id", "")))
    return values[:4]

def _merge_named_modules(semantic_modules: list[dict]) -> list[dict]:
    merged: list[dict] = []
    by_name: dict[str, dict] = {}
    for module in semantic_modules:
        key = module.get("name", "")
        existing = by_name.get(key)
        if not existing:
            clone = dict(module)
            clone["entry_functions"] = list(module.get("entry_functions", []))
            clone["member_symbols"] = list(module.get("member_symbols", []))
            clone["source_dirs"] = list(module.get("source_dirs", []))
            clone["cross_module_edges"] = []
            by_name[key] = clone
            merged.append(clone)
            continue
        existing["entry_functions"] = _merge_entry_functions(
            existing.get("entry_functions", []),
            module.get("entry_functions", []),
        )
        existing["member_symbols"] = sorted(
            set(existing.get("member_symbols", [])) | set(module.get("member_symbols", []))
        )
        existing["source_dirs"] = sorted(
            set(existing.get("source_dirs", [])) | set(module.get("source_dirs", []))
        )
        if not existing.get("responsibility_hint") and module.get("responsibility_hint"):
            existing["responsibility_hint"] = module["responsibility_hint"]

    for index, module in enumerate(merged, 1):
        module["id"] = f"sm_{index:03d}"
    return merged

def _merge_singleton_islands(semantic_modules: list[dict]) -> list[dict]:
    if len(semantic_modules) <= 7:
        return semantic_modules
    modules = [dict(module) for module in semantic_modules]
    while len(modules) > 7:
        modules.sort(key=lambda item: (len(item.get("member_symbols", [])), len(item.get("entry_functions", []))))
        island = modules[0]
        target = None
        shared_dirs = set(island.get("source_dirs", []))
        for candidate in modules[1:]:
            if shared_dirs & set(candidate.get("source_dirs", [])):
                target = candidate
                break
        if target is None:
            target = modules[1]
        target["entry_functions"] = _merge_entry_functions(
            target.get("entry_functions", []),
            island.get("entry_functions", []),
        )
        target["member_symbols"] = sorted(
            set(target.get("member_symbols", [])) | set(island.get("member_symbols", []))
        )
        target["source_dirs"] = sorted(
            set(target.get("source_dirs", [])) | set(island.get("source_dirs", []))
        )
        if not target.get("responsibility_hint") and island.get("responsibility_hint"):
            target["responsibility_hint"] = island["responsibility_hint"]
        modules.pop(0)
    for index, module in enumerate(modules, 1):
        module["id"] = f"sm_{index:03d}"
        module["cross_module_edges"] = []
    return modules

def _symbol_source_dir(symbol_id: str) -> str:
    file_part = symbol_id.split("::", 1)[0].replace("\\", "/")
    if "/" not in file_part:
        return "."
    return file_part.split("/", 1)[0] + "/"

def _rebuild_membership(semantic_modules: list[dict]) -> dict[str, str]:
    membership = {}
    for module in semantic_modules:
        for symbol_id in module.get("member_symbols", []):
            membership[symbol_id] = module["id"]
    return membership

def _pick_primary_entry(module: dict) -> str:
    entries = module.get("entry_functions", [])
    if not entries:
        members = module.get("member_symbols", [])
        return members[0] if members else ""

    def score(item: dict) -> tuple[int, str]:
        signal = item.get("signal", "")
        symbol_id = item.get("symbol_id", "")
        symbol_tail = symbol_id.split("::")[-1]
        confidence = item.get("confidence", "low")
        if symbol_tail.endswith("handle_request"):
            return (-1, symbol_id)
        if "dispatch_source" in signal:
            return (0, symbol_id)
        if "cli" in signal:
            return (1, symbol_id)
        if "dispatch" in signal:
            return (2, symbol_id)
        rank = {"high": 3, "medium": 4, "low": 5}
        return (rank.get(confidence, 6), symbol_id)

    best = sorted(entries, key=score)[0]
    return best.get("symbol_id", "")

def _refresh_module_names(semantic_modules: list[dict], anchors: dict) -> None:
    for module in semantic_modules:
        primary_entry = _pick_primary_entry(module)
        if primary_entry:
            module["name"] = _guess_module_name(primary_entry, anchors)
