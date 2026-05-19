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

from shared.types import Edge


def _norm(node_id: str) -> str:
    return node_id.replace("\\", "/")


def _callee_target(raw_callee):
    if isinstance(raw_callee, dict):
        return raw_callee.get("target", "")
    return raw_callee


def _callee_seq(raw_callee) -> int:
    if isinstance(raw_callee, dict):
        return raw_callee.get("seq", 0)
    return 0


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


def _resolve_id(raw_ref: str, id_index: dict):
    ref = _norm(str(raw_ref or ""))
    if "::" not in ref:
        return None
    return id_index.get(ref)


def _edge_hash(from_id: str, to_id: str) -> str:
    return hashlib.md5((from_id + to_id).encode("utf-8")).hexdigest()[:8]


def _is_virtual_id(node_id: str) -> bool:
    return "#" in node_id


def _build_virtual_skip_pairs(anchors: dict) -> set[tuple[str, str]]:
    """收集 (parent_func_id, callee_id) 对：callee 通过虚拟块调用，不应再建直接边。"""
    skip_pairs = set()
    for anchor in anchors.values():
        if not getattr(anchor, "is_virtual", False):
            continue
        parent_id = getattr(anchor, "parent_anchor", None)
        if not parent_id:
            continue
        for raw_callee in getattr(anchor, "callees", []):
            target = _callee_target(raw_callee)
            if target:
                skip_pairs.add((_norm(parent_id), _norm(target)))
    return skip_pairs


def generate_relations(root: str = ".") -> dict:
    root_path = Path(root)
    output_path = root_path / ".codedendrite" / "relations.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # edge_map: (from_id, to_id, edge_type, condition, scope_label) -> Edge
    # 同一对节点的多次调用合并 seq 列表
    edge_map: dict[tuple, Edge] = {}
    failed: list[str] = []

    def _add_edge(edge: Edge) -> None:
        if edge.edge_type == "dispatch" or edge.condition or edge.scope_label:
            key = (
                edge.from_id,
                edge.to_id,
                edge.edge_type,
                edge.condition,
                edge.dispatch_key,
                edge.dispatch_value,
                edge.scope_label,
            )
        else:
            key = (edge.from_id, edge.to_id, edge.edge_type, None, None, None, None)

        if key in edge_map:
            edge_map[key].seq.extend(s for s in edge.seq if s not in edge_map[key].seq)
        else:
            edge_map[key] = edge

    try:
        from api.anchors import load_anchors

        anchors = load_anchors(str(root_path))
        id_index = _build_id_index(anchors)
        skip_pairs = _build_virtual_skip_pairs(anchors)

        # 预构建 (caller_id, callee_id) -> [seq, ...] 映射，用于 call 边的 seq
        callee_seq_map: dict[tuple[str, str], list[int]] = defaultdict(list)
        for anchor in anchors.values():
            norm_anchor_id = _norm(anchor.id)
            for raw_callee in anchor.callees:
                target = _callee_target(raw_callee)
                if target:
                    seq_val = _callee_seq(raw_callee)
                    callee_seq_map[(_norm(norm_anchor_id), _norm(target))].append(seq_val)

        # 1) Regular call edges from reverse callers.
        for anchor in anchors.values():
            if anchor.is_virtual:
                continue
            for caller_id in anchor.callers:
                caller = _resolve_id(caller_id, id_index)
                if not caller or caller.is_virtual:
                    continue
                from_id = _norm(caller.id)
                to_id = _norm(anchor.id)
                if (from_id, to_id) in skip_pairs:
                    continue  # callee 通过虚拟块路由，不建直接边
                seq_list = callee_seq_map.get((from_id, to_id), [])
                _add_edge(Edge(
                    from_id=from_id,
                    to_id=to_id,
                    edge_type="call",
                    data_in=", ".join(i.get("type", "") for i in anchor.inputs if i.get("type")),
                    data_out=", ".join(o.get("type", "") for o in anchor.outputs if o.get("type")),
                    outer_hash=_edge_hash(from_id, to_id),
                    seq=seq_list,
                ))

        # 2) Inheritance edges.
        for anchor in anchors.values():
            if anchor.symbol_type != "class":
                continue
            for parent in anchor.parent_classes:
                parent_anchor = _resolve_id(parent, id_index)
                to_id = _norm(parent_anchor.id) if parent_anchor else _norm(parent)
                _add_edge(Edge(
                    from_id=_norm(anchor.id),
                    to_id=to_id,
                    edge_type="inherit",
                    data_in="class inherit",
                    data_out="inherited methods+attrs",
                ))

        for anchor in anchors.values():
            if anchor.symbol_type == "method" and anchor.overrides:
                _add_edge(Edge(
                    from_id=_norm(anchor.id),
                    to_id="override::{}".format(anchor.overrides),
                    edge_type="inherit",
                    data_in="override",
                    data_out=anchor.overrides,
                ))

        # 3) Dataflow edges from anchor.callees.
        for anchor in anchors.values():
            if anchor.is_virtual:
                continue
            for raw_callee in anchor.callees:
                callee_id = _callee_target(raw_callee)
                if not callee_id:
                    continue
                callee = _resolve_id(callee_id, id_index)
                if not callee or callee.is_virtual:
                    continue
                if (_norm(anchor.id), _norm(callee.id)) in skip_pairs:
                    continue  # callee 通过虚拟块路由，不建直接数据流边
                _add_edge(Edge(
                    from_id=_norm(anchor.id),
                    to_id=_norm(callee.id),
                    edge_type="dataflow",
                    data_in=", ".join(o.get("type", "") for o in anchor.outputs if o.get("type")),
                    data_out=", ".join(i.get("type", "") for i in callee.inputs if i.get("type")),
                ))

        # 4) Impact edges inferred from call/dataflow fan-in.
        dependents = defaultdict(set)
        for edge in edge_map.values():
            if edge.edge_type in ("call", "dataflow"):
                from_parts = edge.from_id.replace("\\", "/").split("/")
                from_module = from_parts[0] if from_parts else edge.from_id.split("::")[0]
                dependents[edge.to_id].add(from_module)
        for to_id, modules in dependents.items():
            if len(modules) >= 2:
                _add_edge(Edge(
                    from_id="impact::risk",
                    to_id=to_id,
                    edge_type="impact",
                    data_in="{} modules depend on target".format(len(modules)),
                    data_out=", ".join(sorted(modules)),
                ))

        # 5) Dispatch edges.
        try:
            from codeGenome.string_dispatch import find_string_dispatches

            for dispatch in find_string_dispatches(str(root_path)):
                _add_edge(Edge(
                    from_id=dispatch["from_id"],
                    to_id=dispatch["to_id"],
                    edge_type="dispatch",
                    data_in=dispatch.get("data_in", "string route"),
                    data_out=dispatch.get("data_out", "conditional call"),
                    condition=dispatch.get("condition"),
                    dispatch_key=dispatch.get("dispatch_key"),
                    dispatch_value=dispatch.get("dispatch_value"),
                    is_conditional=dispatch.get("is_conditional", True),
                ))
        except Exception as ex:
            failed.append("dispatch edges: {}".format(ex))

        # 6) Virtual block edges:
        #    - 只建 func -> 最外层 vblock（parent 是真实函数的 vblock）
        #    - 建 vblock -> real_func（vblock 的直接真实函数 callee，供影响面反查）
        #    - 不建 vblock -> child_vblock（子块透视由 flatten_virtual 走 anchors）
        for anchor in anchors.values():
            if not anchor.is_virtual:
                continue

            # func -> outermost_vblock：仅当 parent 是非虚拟节点时才加
            if anchor.parent_anchor:
                parent = _resolve_id(anchor.parent_anchor, id_index)
                if parent and not parent.is_virtual:
                    seq_list = callee_seq_map.get((_norm(anchor.parent_anchor), _norm(anchor.id)), [])
                    _add_edge(Edge(
                        from_id=_norm(anchor.parent_anchor),
                        to_id=_norm(anchor.id),
                        edge_type="call",
                        data_in="control entry",
                        data_out=anchor.virtual_kind or "virtual block",
                        scope_label=anchor.scope_label,
                        seq=seq_list,
                    ))

            # vblock -> real_func：只加真实函数 callee，跳过嵌套 vblock
            for raw_callee in anchor.callees:
                target_id = _callee_target(raw_callee)
                target_anchor = _resolve_id(target_id, id_index)
                if not target_anchor or target_anchor.is_virtual:
                    continue
                _condition = raw_callee.get("condition") if isinstance(raw_callee, dict) else None
                _scope = raw_callee.get("scope_label") if isinstance(raw_callee, dict) else None
                _seq = _callee_seq(raw_callee)
                _add_edge(Edge(
                    from_id=_norm(anchor.id),
                    to_id=_norm(target_anchor.id),
                    edge_type="call",
                    data_in=anchor.virtual_kind or "control block",
                    data_out="conditional call" if _condition else "nested call",
                    condition=_condition,
                    is_conditional=bool(_condition),
                    scope_label=_scope,
                    seq=[_seq],
                ))

    except Exception as ex:
        failed.append("relation generation: {}".format(ex))

    edges = list(edge_map.values())
    by_type = dict(Counter(edge.edge_type for edge in edges))
    for name in ["call", "inherit", "dataflow", "impact", "dispatch"]:
        by_type.setdefault(name, 0)

    data = {
        "edges": [asdict(edge) for edge in edges],
        "meta": {
            "total_edges": len(edges),
            "by_type": by_type,
            "failed": failed,
        },
    }
    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, indent=2, ensure_ascii=False)

    return {
        "total": len(edges),
        "by_type": by_type,
        "failed": failed,
    }


def load_relations(root: str = ".") -> dict:
    path = Path(root) / ".codedendrite" / "relations.json"
    if not path.exists():
        raise FileNotFoundError("Run generate_relations(root='{}') first".format(root))
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


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


def expand_node(node_id: str, root: str = ".", radius: int = 1) -> dict:
    """展开节点的直接边。遇到虚拟块 out-edge 时自动透视，显示其叶子函数。

    若展开行数 * 2 > 虚拟块源码行数，改为附带源码片段 + 叶子函数 anchor 列表。
    """
    visited = set()

    def _load_anchors_once():
        try:
            from api.anchors import load_anchors
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


def count_edge_types(root: str = ".") -> dict:
    data = load_relations(root)
    return dict(Counter(edge.get("edge_type", "?") for edge in data.get("edges", [])))


__all__ = [
    "generate_relations",
    "load_relations",
    "get_node_edges",
    "expand_node",
    "flatten_virtual",
    "filter_edges_by_keyword",
    "count_edge_types",
]
