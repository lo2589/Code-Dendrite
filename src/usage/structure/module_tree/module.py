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

from usage.structure.module_tree.backfill_module_tree_responsibilities import _backfill_module_tree_responsibilities
from usage.structure.module_tree.compute_call_structure_hash import _build_semantic_modules, _collect_dispatch_sources, _collect_dispatch_targets, _compute_call_structure_hash, _find_cli_entries, _is_noise_anchor, _normalize_anchors, _normalize_relations, _normalize_symbol_id, _normalize_symbol_word, _read_json, _render_project_summary

def _score_entries(
    anchors: dict,
    relations: dict,
    cli_entries: set[str],
    dispatch_targets: set[str],
    dispatch_sources: dict[str, int],
) -> list[dict]:
    incoming = Counter()
    outgoing = Counter()
    for edge in relations.get("edges", []):
        edge_type = edge.get("edge_type")
        if edge_type not in EXPAND_EDGE_TYPES:
            continue
        from_id = edge.get("from_id", "")
        to_id = edge.get("to_id", "")
        if from_id:
            outgoing[from_id] += 1
        if to_id:
            incoming[to_id] += 1

    scored = []
    for anchor in anchors.values():
        symbol_id = anchor.id
        symbol = anchor.symbol or ""
        if _is_noise_anchor(anchor):
            continue
        signals: list[str] = []
        score = 0
        confidence = "low"
        if symbol_id in dispatch_targets:
            signals.append("dispatch")
            score += 4
            confidence = "high"
        dispatch_fanout = dispatch_sources.get(symbol_id, 0)
        if dispatch_fanout >= 2:
            signals.append("dispatch_source")
            score += 5 + min(dispatch_fanout, 4)
            confidence = "high"
        if symbol_id in cli_entries:
            signals.append("cli")
            score += 4
            confidence = "high"
        if (
            anchor.symbol_type in {"function", "method"}
            and not symbol.startswith("_")
            and incoming[symbol_id] <= 1
            and outgoing[symbol_id] >= 2
        ):
            signals.append("fanout")
            score += 2
            if confidence != "high":
                confidence = "medium"
        if score <= 0:
            continue
        scored.append(
            {
                "symbol_id": symbol_id,
                "score": score,
                "signals": signals,
                "confidence": confidence,
            }
        )

    scored.sort(key=lambda item: (-item["score"], item["symbol_id"]))
    return scored

def _summarize_module(module: dict) -> str:
    entries = [
        entry.get("symbol_id", "").split("::")[-1]
        for entry in module.get("entry_functions", [])
        if entry.get("symbol_id")
    ]
    members = [
        symbol_id.split("::")[-1]
        for symbol_id in module.get("member_symbols", [])
    ]
    words = entries or members
    normalized = [_normalize_symbol_word(item) for item in words[:4]]
    normalized = [item for item in normalized if item]
    if not normalized:
        return "Provide module navigation"
    if len(normalized) == 1:
        return f"Handle {normalized[0]}"
    return "Coordinate " + ", ".join(normalized[:3])

def _summarize_project(project_name: str, modules: list[dict]) -> str:
    names = [module.get("name", "") for module in modules if module.get("name")]
    names = [name.replace("_", " ") for name in names[:3]]
    if not names:
        return f"Organize {project_name} modules"
    if len(names) == 1:
        return f"Coordinate {names[0]} workflows"
    return "Coordinate " + ", ".join(names[:2]) + " workflows"

def load_module_tree(root: str = ".") -> dict:
    path = Path(root) / ".codedendrite" / "module_tree.json"
    if not path.exists():
        raise FileNotFoundError(
            "先执行 generate_module_tree(root='{}')".format(root)
        )
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _available_modules(root: str) -> list[dict]:
    """Expose one query contract for both generations of module evidence.

    The phase-1 tree intentionally accepts only strong fan-out entries. Small
    repositories can have a useful V2 capability module without any phase-1
    entries; the human-facing queries must still be able to navigate it.
    """
    classic = load_module_tree(root).get("semantic_modules", [])
    if classic:
        return classic

    index_dir = Path(root) / ".codedendrite"
    v2_path = index_dir / "module_tree_v2.json"
    inputs = [index_dir / "anchors.json", index_dir / "relations.json"]
    stale = not v2_path.exists() or any(
        path.exists() and path.stat().st_mtime_ns > v2_path.stat().st_mtime_ns
        for path in inputs
    )
    if stale:
        from usage.structure.module_tree_v2 import generate_module_tree_v2, save_module_tree_v2
        v2 = generate_module_tree_v2(root)
        save_module_tree_v2(v2, root)
    else:
        v2 = json.loads(v2_path.read_text(encoding="utf-8"))

    v2_modules = v2.get("modules", [])
    file_owners: dict[str, set[str]] = defaultdict(set)
    for module in v2_modules:
        for file_name in module.get("files", []):
            file_owners[file_name].add(module["id"])

    anchors = load_anchors(root)
    result = []
    for module in v2_modules:
        members = set(module.get("functions", [])) | set(module.get("entrypoints", []))
        members.update(module.get("evidence", {}).get("classes", []))
        for anchor_id, anchor in anchors.items():
            if file_owners.get(anchor.file) == {module["id"]}:
                members.add(anchor_id)
        result.append({
            "id": module["id"],
            "name": module.get("name", ""),
            "responsibility": module.get("what", ""),
            "entry_functions": [
                {"symbol_id": symbol_id} for symbol_id in module.get("entrypoints", [])
            ],
            "member_symbols": sorted(members),
            "source": "module_tree_v2",
            "confidence": module.get("confidence", ""),
        })
    return result

def find_module_for_symbol(symbol_id_or_name: str, root: str = ".") -> dict | None:
    target = _normalize_symbol_id(symbol_id_or_name)
    best_match = None
    best_score = -1
    for module in _available_modules(root):
        score = 0
        for symbol_id in module.get("member_symbols", []):
            if symbol_id == target:
                return module
            symbol_tail = symbol_id.split("::")[-1]
            if target == symbol_tail or target.endswith(f"::{symbol_tail}"):
                score = max(score, 3)
            elif symbol_tail.endswith(f".{target}") or target in symbol_tail:
                score = max(score, 2)
            elif target in symbol_id:
                score = max(score, 1)
        if score > best_score:
            best_match = module
            best_score = score
    return best_match if best_score > 0 else None

def generate_module_summary(root: str = ".") -> dict:
    """
    Phase 2 minimal implementation:
      - reuse summary_cache.json when call_structure_hash is unchanged
      - otherwise build deterministic summaries from module_tree.json
      - write project_summary.md and backfill module_tree responsibilities
    """
    root_path = Path(root)
    codedendrite_dir = root_path / ".codedendrite"
    module_tree = load_module_tree(str(root_path))
    structure_hash = module_tree.get("call_structure_hash", "")
    cache_path = codedendrite_dir / "summary_cache.json"
    summary_path = codedendrite_dir / "project_summary.md"

    cached = _read_json(cache_path)
    reused = bool(cached and cached.get("call_structure_hash") == structure_hash)
    reused = reused and cached.get("summary_version") == SUMMARY_VERSION
    if reused:
        summary_data = cached
    else:
        modules = []
        for module in module_tree.get("semantic_modules", []):
            modules.append(
                {
                    "id": module.get("id"),
                    "name": module.get("name"),
                    "responsibility": _summarize_module(module),
                }
            )
        project_one_line = _summarize_project(root_path.name, modules)
        summary_data = {
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "summary_version": SUMMARY_VERSION,
            "call_structure_hash": structure_hash,
            "project_name": root_path.name,
            "project_one_line": project_one_line,
            "modules": modules,
        }
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(summary_data, f, ensure_ascii=False, indent=2)

    _backfill_module_tree_responsibilities(
        module_tree=module_tree,
        summary_data=summary_data,
        output_path=codedendrite_dir / "module_tree.json",
    )
    summary_markdown = _render_project_summary(module_tree, summary_data)
    summary_path.write_text(summary_markdown, encoding="utf-8")
    summary_data["reused_cache"] = reused
    return summary_data

def generate_module_tree(root: str = ".") -> dict:
    # 延迟导入：api 层的 __init__ 会反过来 import 本模块，
    # 模块级导入 api.relations 会形成环。
    from api.relations import load_relations

    root_path = Path(root)
    codedendrite_dir = root_path / ".codedendrite"
    codedendrite_dir.mkdir(parents=True, exist_ok=True)

    anchors = _normalize_anchors(load_anchors(str(root_path)))
    relations = _normalize_relations(load_relations(str(root_path)))
    cli_entries = _find_cli_entries(root_path, anchors)
    dispatch_targets = _collect_dispatch_targets(relations)
    dispatch_sources = _collect_dispatch_sources(relations)
    scored_entries = _score_entries(
        anchors,
        relations,
        cli_entries,
        dispatch_targets,
        dispatch_sources,
    )
    semantic_modules, module_membership = _build_semantic_modules(
        anchors=anchors,
        relations=relations,
        scored_entries=scored_entries,
    )

    structure_hash = _compute_call_structure_hash(semantic_modules)
    data = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "phase": 1,
        "call_structure_hash": structure_hash,
        "semantic_modules": semantic_modules,
    }

    with open(codedendrite_dir / "module_tree.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    return data

def get_module(module_id_or_name: str, root: str = ".") -> dict | None:
    modules = _available_modules(root)
    for module in modules:
        if module.get("id") == module_id_or_name or module.get("name") == module_id_or_name:
            return module
    lowered = module_id_or_name.lower()
    for module in modules:
        name = str(module.get("name", "")).lower()
        if lowered and lowered in name:
            return module
    return None

def load_summary_cache(root: str = ".") -> dict:
    path = Path(root) / ".codedendrite" / "summary_cache.json"
    if not path.exists():
        raise FileNotFoundError(
            "先执行 generate_module_summary(root='{}')".format(root)
        )
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def query_modules(query: str, root: str = ".", limit: int = 5) -> list[dict]:
    terms = [item for item in query.lower().split() if item]
    scored = []
    for module in _available_modules(root):
        haystacks = [
            str(module.get("id", "")),
            str(module.get("name", "")),
            str(module.get("responsibility", "")),
            str(module.get("responsibility_hint", "")),
            " ".join(item.get("symbol_id", "") for item in module.get("entry_functions", [])),
            " ".join(module.get("member_symbols", [])),
        ]
        combined = " ".join(haystacks).lower()
        score = 0
        for term in terms:
            if term in str(module.get("name", "")).lower():
                score += 4
            elif term in str(module.get("responsibility", "")).lower():
                score += 3
            elif term in combined:
                score += 1
        if score > 0:
            scored.append((score, module))
    scored.sort(key=lambda item: (-item[0], item[1].get("name", "")))
    return [module for _, module in scored[:limit]]
