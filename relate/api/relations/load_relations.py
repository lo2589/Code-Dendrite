"""
Relations API.

Generate and query the persisted relation graph in `.codedendrite/relations.json`.
"""

from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from dataclasses import asdict
from pathlib import Path
from typing import List, Optional

from base.shared.types import Edge

__all__ = [
    "generate_relations",
    "load_relations",
    "get_node_edges",
    "expand_node",
    "flatten_virtual",
    "filter_edges_by_keyword",
    "count_edge_types",
]

def _norm(node_id: str) -> str:
    return node_id.replace("\\", "/")

def _build_id_index(anchors: dict) -> dict:
    index = {}
    for anchor in anchors.values():
        index[_norm(anchor.id)] = anchor
    return index

def _build_unique_symbol_index(anchors: dict) -> dict:
    by_symbol = {}
    duplicate_symbols = set()
    for anchor in anchors.values():
        symbol = anchor.symbol
        if not symbol:
            continue
        if symbol in by_symbol:
            duplicate_symbols.add(symbol)
        else:
            by_symbol[symbol] = anchor
    return {
        symbol: anchor
        for symbol, anchor in by_symbol.items()
        if symbol not in duplicate_symbols
    }

def _callee_target(raw_callee):
    if isinstance(raw_callee, dict):
        return raw_callee.get("target", "")
    return raw_callee

def _iter_call_refs(anchor):
    sites = list(getattr(anchor, "call_sites", []) or [])
    if sites:
        return sites
    return [
        {"target": _callee_target(raw), "seq": idx}
        for idx, raw in enumerate(getattr(anchor, "callees", []) or [])
    ]

def _build_virtual_skip_pairs(anchors: dict) -> set[tuple[str, str]]:
    """收集 (parent_func_id, callee_id) 对：callee 通过虚拟块调用，不应再建直接边。"""
    skip_pairs = set()
    for anchor in anchors.values():
        if not getattr(anchor, "is_virtual", False):
            continue
        parent_id = getattr(anchor, "parent_anchor", None)
        if not parent_id:
            continue
        for raw_callee in _iter_call_refs(anchor):
            target = _callee_target(raw_callee)
            if target:
                skip_pairs.add((_norm(parent_id), _norm(target)))
    return skip_pairs

def _callee_condition(raw_callee) -> Optional[str]:
    if not isinstance(raw_callee, dict):
        return None
    conds = raw_callee.get("conds")
    if conds and conds != ["nocond"]:
        return json.dumps(conds, ensure_ascii=False, separators=(",", ":"))
    return raw_callee.get("condition")

def _callee_seq(raw_callee) -> int:
    if isinstance(raw_callee, dict):
        return raw_callee.get("seq", 0)
    return 0

def _edge_hash(from_id: str, to_id: str) -> str:
    return hashlib.md5((from_id + to_id).encode("utf-8")).hexdigest()[:8]

def _is_virtual_id(node_id: str) -> bool:
    return "#" in node_id

def _resolve_id(raw_ref: str, id_index: dict):
    ref = _norm(str(raw_ref or ""))
    if "::" not in ref:
        return None
    return id_index.get(ref)

def load_relations(root: str = ".") -> dict:
    path = Path(root) / ".codedendrite" / "relations.json"
    if not path.exists():
        raise FileNotFoundError("Run generate_relations(root='{}') first".format(root))
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)

def count_edge_types(root: str = ".") -> dict:
    data = load_relations(root)
    return dict(Counter(edge.get("edge_type", "?") for edge in data.get("edges", [])))

def get_node_edges(
    node_id: str,
    root: str = ".",
    direction: str = "both",
    edge_type: Optional[str] = None,
) -> list:
    data = load_relations(root)
    nid = _norm(node_id)
    result = []
    for edge in data["edges"]:
        if edge_type and edge["edge_type"] != edge_type:
            continue
        if direction in ("in", "both") and _norm(edge["to_id"]) == nid:
            result.append({**edge, "direction": "in"})
        if direction in ("out", "both") and _norm(edge["from_id"]) == nid:
            result.append({**edge, "direction": "out"})
    return result

def flatten_virtual(vblock_id: str, anchors: dict, path: list | None = None) -> list[dict]:
    """递归展开虚拟块，返回所有叶子真实函数，带路径标注。

    返回: [{path, func_id, seq, condition, scope_label, line}, ...]
    path 格式: "cond_block_1::loop_block_2::func_name"
    """
    if path is None:
        path = []
    anchor = anchors.get(vblock_id)
    if not anchor:
        return []
    result = []
    for raw_callee in anchor.callees:
        target = _callee_target(raw_callee)
        if not target:
            continue
        meta = raw_callee if isinstance(raw_callee, dict) else {}
        callee_anchor = anchors.get(target)
        if callee_anchor and getattr(callee_anchor, "is_virtual", False):
            child_path = path + [callee_anchor.symbol]
            result.extend(flatten_virtual(target, anchors, child_path))
        else:
            func_label = target.split("::")[-1] if "::" in target else target
            result.append({
                "path": "::".join(path + [func_label]) if path else func_label,
                "func_id": target,
                "seq": meta.get("seq"),
                "condition": meta.get("condition"),
                "scope_label": meta.get("scope_label"),
                "line": meta.get("line"),
            })
    return result

def expand_node(node_id: str, root: str = ".", radius: int = 1) -> dict:
    """展开节点的直接边。遇到虚拟块 out-edge 时自动透视，显示其叶子函数。

    若展开行数 * 2 > 虚拟块源码行数，改为附带源码片段 + 叶子函数 anchor 列表。
    """
    visited = set()

    def _load_anchors_once():
        try:
            from index.api.anchors import load_anchors
            return load_anchors(root)
        except Exception:
            return {}

    anchors_cache: dict = {}

    def _get_anchors() -> dict:
        if not anchors_cache:
            anchors_cache.update(_load_anchors_once())
        return anchors_cache

    def _expand(nid: str, depth: int) -> dict:
        if depth == 0 or nid in visited:
            return {"id": nid, "edges": []}
        visited.add(nid)
        node_edges = get_node_edges(nid, root)

        expanded_edges = []
        for edge in node_edges:
            target_id = edge["to_id"] if edge["direction"] == "out" else edge["from_id"]
            edge_entry = dict(edge)

            # 出边指向虚拟块时：透视展开
            if edge["direction"] == "out" and _is_virtual_id(target_id):
                anchors = _get_anchors()
                vblock = anchors.get(target_id) or anchors.get(_norm(target_id))
                flat = flatten_virtual(target_id, anchors)
                flat_lines = len(flat)
                src_lines = 0
                if vblock:
                    src_lines = max(0, (vblock.line_end or 0) - (vblock.line_start or 0))

                if flat_lines * 2 > src_lines and src_lines > 0:
                    # 展开太长，给源码 + 叶子 anchor 列表
                    try:
                        file_path = str(Path(root) / vblock.file) if vblock else None
                        source_lines: list[str] = []
                        if file_path:
                            all_lines = Path(file_path).read_text(encoding="utf-8", errors="ignore").splitlines()
                            lo = max(0, (vblock.line_start or 1) - 1)
                            hi = min(len(all_lines), vblock.line_end or lo + 1)
                            source_lines = [
                                "{:4d}  {}".format(lo + 1 + i, l)
                                for i, l in enumerate(all_lines[lo:hi])
                            ]
                    except Exception:
                        source_lines = []
                    leaf_anchors = [
                        {"func_id": f["func_id"], "path": f["path"], "seq": f["seq"]}
                        for f in flat
                    ]
                    edge_entry["virtual_expanded"] = "source"
                    edge_entry["source_snippet"] = "\n".join(source_lines)
                    edge_entry["leaf_anchors"] = leaf_anchors
                else:
                    edge_entry["virtual_expanded"] = "flat"
                    edge_entry["flat_callees"] = flat

                edge_entry["target"] = {"id": target_id, "edges": []}
            else:
                edge_entry["target"] = _expand(target_id, depth - 1)

            expanded_edges.append(edge_entry)

        return {"id": nid, "edges": expanded_edges}

    return _expand(node_id, radius)

def filter_edges_by_keyword(keyword: str, root: str = ".") -> list:
    data = load_relations(root)
    kw = keyword.lower()
    return [
        edge for edge in data.get("edges", [])
        if any(
            kw in str(edge.get(field, "")).lower()
            for field in (
                "from_id",
                "to_id",
                "condition",
                "dispatch_key",
                "dispatch_value",
                "scope_label",
                "data_in",
                "data_out",
            )
        )
    ]
