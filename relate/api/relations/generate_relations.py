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

from relate.api.relations.load_relations import _build_id_index, _build_virtual_skip_pairs, _callee_condition, _callee_seq, _callee_target, _edge_hash, _iter_call_refs, _norm, _resolve_id

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
        from index.api.anchors import load_anchors

        anchors = load_anchors(str(root_path))
        id_index = _build_id_index(anchors)
        skip_pairs = _build_virtual_skip_pairs(anchors)

        # Precompute (caller_id, callee_id) -> call-site refs for edge metadata.
        callee_ref_map: dict[tuple[str, str], list[dict]] = defaultdict(list)
        for anchor in anchors.values():
            norm_anchor_id = _norm(anchor.id)
            for raw_callee in _iter_call_refs(anchor):
                target = _callee_target(raw_callee)
                if target:
                    site = dict(raw_callee) if isinstance(raw_callee, dict) else {"target": target}
                    site.setdefault("seq", _callee_seq(raw_callee))
                    callee_ref_map[(_norm(norm_anchor_id), _norm(target))].append(site)

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
                refs = callee_ref_map.get((from_id, to_id), [])
                if not refs:
                    refs = [{"target": to_id, "seq": 0, "conds": ["nocond"]}]
                for ref in refs:
                    condition = _callee_condition(ref)
                    _add_edge(Edge(
                        from_id=from_id,
                        to_id=to_id,
                        edge_type="call",
                        data_in=", ".join(i.get("type", "") for i in anchor.inputs if i.get("type")),
                        data_out=", ".join(o.get("type", "") for o in anchor.outputs if o.get("type")),
                        outer_hash=_edge_hash(from_id, to_id),
                        condition=condition,
                        is_conditional=bool(condition),
                        seq=[_callee_seq(ref)],
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
            for raw_callee in _iter_call_refs(anchor):
                callee_id = _callee_target(raw_callee)
                if not callee_id:
                    continue
                callee = _resolve_id(callee_id, id_index)
                if not callee or callee.is_virtual:
                    continue
                if (_norm(anchor.id), _norm(callee.id)) in skip_pairs:
                    continue  # callee 通过虚拟块路由，不建直接数据流边
                condition = _callee_condition(raw_callee)
                _add_edge(Edge(
                    from_id=_norm(anchor.id),
                    to_id=_norm(callee.id),
                    edge_type="dataflow",
                    data_in=", ".join(o.get("type", "") for o in anchor.outputs if o.get("type")),
                    data_out=", ".join(i.get("type", "") for i in callee.inputs if i.get("type")),
                    condition=condition,
                    is_conditional=bool(condition),
                    seq=[_callee_seq(raw_callee)],
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
            from parse.codeGenome.string_dispatch import find_string_dispatches

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
                    refs = callee_ref_map.get((_norm(anchor.parent_anchor), _norm(anchor.id)), [])
                    seq_list = [_callee_seq(ref) for ref in refs]
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
            for raw_callee in _iter_call_refs(anchor):
                target_id = _callee_target(raw_callee)
                target_anchor = _resolve_id(target_id, id_index)
                if not target_anchor or target_anchor.is_virtual:
                    continue
                _condition = _callee_condition(raw_callee)
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
