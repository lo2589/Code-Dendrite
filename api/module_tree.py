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

from api.anchors import load_anchors
from api.relations import load_relations


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


def generate_module_tree(root: str = ".") -> dict:
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


def load_module_tree(root: str = ".") -> dict:
    path = Path(root) / ".codedendrite" / "module_tree.json"
    if not path.exists():
        raise FileNotFoundError(
            "先执行 generate_module_tree(root='{}')".format(root)
        )
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


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


def load_summary_cache(root: str = ".") -> dict:
    path = Path(root) / ".codedendrite" / "summary_cache.json"
    if not path.exists():
        raise FileNotFoundError(
            "先执行 generate_module_summary(root='{}')".format(root)
        )
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_module(module_id_or_name: str, root: str = ".") -> dict | None:
    tree = load_module_tree(root)
    modules = tree.get("semantic_modules", [])
    for module in modules:
        if module.get("id") == module_id_or_name or module.get("name") == module_id_or_name:
            return module
    lowered = module_id_or_name.lower()
    for module in modules:
        name = str(module.get("name", "")).lower()
        if lowered and lowered in name:
            return module
    return None


def find_module_for_symbol(symbol_id_or_name: str, root: str = ".") -> dict | None:
    target = _normalize_symbol_id(symbol_id_or_name)
    tree = load_module_tree(root)
    best_match = None
    best_score = -1
    for module in tree.get("semantic_modules", []):
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


def query_modules(query: str, root: str = ".", limit: int = 5) -> list[dict]:
    tree = load_module_tree(root)
    terms = [item for item in query.lower().split() if item]
    scored = []
    for module in tree.get("semantic_modules", []):
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


def _collect_dispatch_targets(relations: dict) -> set[str]:
    return {
        edge.get("to_id", "")
        for edge in relations.get("edges", [])
        if edge.get("edge_type") == "dispatch" and edge.get("to_id")
    }


def _collect_dispatch_sources(relations: dict) -> dict[str, int]:
    counts = Counter()
    for edge in relations.get("edges", []):
        if edge.get("edge_type") != "dispatch":
            continue
        from_id = edge.get("from_id", "")
        if from_id:
            counts[from_id] += 1
    return dict(counts)


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


def _refresh_module_names(semantic_modules: list[dict], anchors: dict) -> None:
    for module in semantic_modules:
        primary_entry = _pick_primary_entry(module)
        if primary_entry:
            module["name"] = _guess_module_name(primary_entry, anchors)


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


def _rebuild_membership(semantic_modules: list[dict]) -> dict[str, str]:
    membership = {}
    for module in semantic_modules:
        for symbol_id in module.get("member_symbols", []):
            membership[symbol_id] = module["id"]
    return membership


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


def _normalize_symbol_word(symbol: str) -> str:
    word = symbol.split(".")[-1]
    for prefix in ("run_", "build_", "handle_", "get_", "set_"):
        if word.startswith(prefix):
            word = word[len(prefix):]
    return word.replace("_", " ").strip()


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


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


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


def _build_responsibility_hint(member_symbols: list[str]) -> str:
    names = [symbol_id.split("::")[-1].split(".")[-1] for symbol_id in member_symbols[:4]]
    return " -> ".join(names)[:120]


def _symbol_source_dir(symbol_id: str) -> str:
    file_part = symbol_id.split("::", 1)[0].replace("\\", "/")
    if "/" not in file_part:
        return "."
    return file_part.split("/", 1)[0] + "/"


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


def _jaccard(left: Iterable[str], right: Iterable[str]) -> float:
    left_set = set(left)
    right_set = set(right)
    if not left_set and not right_set:
        return 1.0
    if not left_set or not right_set:
        return 0.0
    return len(left_set & right_set) / len(left_set | right_set)


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


def _camel_to_snake(name: str) -> str:
    out = []
    for index, ch in enumerate(name):
        if ch.isupper() and index > 0 and (not name[index - 1].isupper()):
            out.append("_")
        out.append(ch.lower())
    return "".join(out)


__all__ = [
    "generate_module_tree",
    "load_module_tree",
    "get_module",
    "find_module_for_symbol",
    "query_modules",
    "generate_module_summary",
    "load_summary_cache",
]
