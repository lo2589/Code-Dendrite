"""
能力候选提取器
========================
从静态证据（锚点 + 关系 + 路径策略）中提取能力候选，
供 module_tree_v2.py 合并成最终模块。

能力候选 = 高层锚点 + 局部邻域证据 + 引用证据 + 打分

用法:
    from synth.api.capability_candidates import build_capability_candidates

    result = build_capability_candidates("/path/to/project")
    # -> { "version": ..., "candidates": [...], "summary": {...} }
"""

import json
import os
from collections import defaultdict
from pathlib import Path
from typing import Optional

from synth.api.path_policy import (
    PathPolicy,
    classify_path_role,
    load_path_policy,
    normalize_project_path,
)


# ── 锚点适配（兼容 Anchor 对象和 dict）──────────────────────────

from synth.api.capability_candidates.count_call_fanout import _count_call_fanin, _count_call_fanout, _count_distinct_caller_files, _get_file_from_id, _infer_area, _is_low_distinctiveness_name, _is_private_symbol, attach_reference_evidence, score_candidate

def _anchor_attr(anchor, key: str, default=""):
    """从 Anchor 对象或 dict 中读取属性。"""
    if isinstance(anchor, dict):
        return anchor.get(key, default)
    return getattr(anchor, key, default)

def _build_edge_indexes(relations: dict) -> tuple:
    """从 relations 构建双向边索引。

    Returns:
        (outgoing, incoming, dispatch_targets)
        outgoing[from_id] = [(to_id, edge_type), ...]
        incoming[to_id]   = [(from_id, edge_type), ...]
        dispatch_targets   = set of to_id that have dispatch edges
    """
    edges = relations.get("edges", [])
    outgoing = defaultdict(list)
    incoming = defaultdict(list)
    dispatch_targets = set()

    for e in edges:
        fid = e.get("from_id", "")
        tid = e.get("to_id", "")
        etype = e.get("edge_type", "")
        if not fid or not tid:
            continue
        outgoing[fid].append((tid, etype))
        incoming[tid].append((fid, etype))
        if etype == "dispatch":
            dispatch_targets.add(tid)

    return outgoing, incoming, dispatch_targets

def _build_file_anchor_index(anchors: dict) -> dict:
    """按文件分组锚点。

    Returns:
        { "file/path.py": [anchor_dict, ...], ... }
    """
    index = defaultdict(list)
    for aid, anchor in anchors.items():
        f = _anchor_attr(anchor, "file", "")
        if f:
            index[f].append(anchor)
    return index

def detect_high_level_anchor(
    symbol_id: str,
    anchor: dict,
    outgoing: dict,
    incoming: dict,
    dispatch_targets: set,
    file_anchor_index: dict,
    policy: PathPolicy,
) -> tuple:
    """判定是否为高层锚点。

    Returns:
        (is_high_level: bool, source_type: str, signals: list[str])
    """
    name = _anchor_attr(anchor, "symbol", "")
    stype = _anchor_attr(anchor, "symbol_type", "")
    fpath = _anchor_attr(anchor, "file", "")

    signals = []
    source_type = ""

    # ── 1. 外部可触发入口 ──
    # dispatch 边目标
    if symbol_id in dispatch_targets:
        signals.append("dispatch_target")
        source_type = source_type or "registry"

    # 被多个不同文件调用
    distinct_callers = _count_distinct_caller_files(symbol_id, incoming)
    if distinct_callers >= 3:
        signals.append(f"multi_file_callers({distinct_callers})")
        source_type = source_type or "external_entry"

    # ── 2. 编排器模式（高 fanout）──
    fanout = _count_call_fanout(symbol_id, outgoing)
    if fanout >= 4:
        signals.append(f"high_fanout({fanout})")
        source_type = source_type or "orchestrator"

    # ── 3. 组件根（文件的主类或主函数）──
    if stype == "class":
        # 类本身是天然的组件根
        signals.append("class_root")
        source_type = source_type or "component_root"
    elif stype == "function" and not _is_private_symbol(name):
        # 检查是否是文件的主要公开函数
        file_anchors = file_anchor_index.get(fpath, [])
        public_functions = [
            a for a in file_anchors
            if _anchor_attr(a, "symbol_type") == "function"
            and not _is_private_symbol(_anchor_attr(a, "symbol", ""))
        ]
        # 如果该文件公开函数较少（<=3），此函数可视为组件根
        if len(public_functions) <= 3:
            signals.append("file_primary_function")
            source_type = source_type or "component_root"

    # ── 排除低层信号 ──
    if _is_private_symbol(name):
        signals.append("private_symbol")
    if _is_low_distinctiveness_name(name):
        signals.append("low_distinctiveness_name")

    # ── 判定 ──
    # method 类型需要额外信号才能升级
    if stype == "method":
        # method 必须有至少 2 个正面信号（不含 class_root）才能成为候选
        positive = [s for s in signals if not s.startswith(("private", "low_"))]
        is_high = len(positive) >= 2
    else:
        # function / class 有至少 1 个正面信号即可
        positive = [s for s in signals if not s.startswith(("private", "low_"))]
        is_high = len(positive) >= 1

    # 但如果有强排除信号，降级
    if _is_private_symbol(name) and "dispatch_target" not in signals:
        is_high = False
    if _is_low_distinctiveness_name(name) and len(signals) <= 2:
        is_high = False

    if not source_type:
        source_type = "area"

    return is_high, source_type, signals

def _infer_candidate_name(anchor: dict, source_type: str) -> str:
    """推断候选名称。

    优先级: 类名 > 文件名语义 > 符号名
    """
    name = _anchor_attr(anchor, "symbol", "")
    stype = _anchor_attr(anchor, "symbol_type", "")
    fpath = _anchor_attr(anchor, "file", "")

    # 类直接用类名
    if stype == "class":
        return name

    # 函数：尝试用文件名作为语义前缀
    fname = Path(fpath).stem
    if fname and fname != "__init__" and fname != name:
        return f"{fname}::{name}"

    return name

def build_candidate_seed(
    symbol_id: str,
    anchor: dict,
    source_type: str,
    signals: list,
    policy: PathPolicy,
) -> dict:
    """为一个高层锚点构建候选种子。"""
    fpath = _anchor_attr(anchor, "file", "")
    area = _infer_area(fpath)
    name_candidate = _infer_candidate_name(anchor, source_type)

    notes = []
    if _is_low_distinctiveness_name(_anchor_attr(anchor, "symbol", "")):
        notes.append("low_semantic_name")

    return {
        "id": f"cap_{symbol_id.replace('::', '__').replace('/', '_')}",
        "name_candidate": name_candidate,
        "module_hint": "",
        "source_type": source_type,
        "area": area,
        "policy": classify_path_role(fpath, policy),
        "score": 0,
        "entrypoints": [symbol_id],
        "classes": [symbol_id] if _anchor_attr(anchor, "symbol_type") == "class" else [],
        "symbols": [symbol_id],
        "files": [fpath],
        "evidence": {
            "directories": [area] if area else [],
            "relations": [],
            "references": [],
            "tests": [],
            "docs": [],
        },
        "signals": signals,
        "notes": notes,
    }

def attach_relation_evidence(
    candidates: list,
    anchors: dict,
    outgoing: dict,
    incoming: dict,
    policy: PathPolicy,
    max_depth: int = 1,
) -> list:
    """为每个候选挂载关系图证据（直接邻居）。"""
    for cand in candidates:
        seen_symbols = set(cand["symbols"])
        seen_files = set(cand["files"])
        relation_evidence = []

        for entry_id in cand["entrypoints"]:
            # 出边（callees）
            for to_id, etype in outgoing.get(entry_id, []):
                to_file = _get_file_from_id(to_id)
                role = classify_path_role(to_file, policy) if to_file else "normal"

                if role == "exclude":
                    continue

                relation_evidence.append({
                    "from": entry_id,
                    "to": to_id,
                    "edge_type": etype,
                    "direction": "outgoing",
                })

                if role == "reference_only":
                    # 测试/示例只进 evidence.tests
                    if to_id not in seen_symbols:
                        cand["evidence"]["tests"].append(to_id)
                else:
                    if to_id not in seen_symbols:
                        cand["symbols"].append(to_id)
                        seen_symbols.add(to_id)
                    if to_file and to_file not in seen_files:
                        cand["files"].append(to_file)
                        seen_files.add(to_file)

                    # 如果邻居是类，也记录
                    neighbor = anchors.get(to_id, None)
                    if neighbor and _anchor_attr(neighbor, "symbol_type") == "class" and to_id not in cand["classes"]:
                        cand["classes"].append(to_id)

            # 入边（callers）
            for from_id, etype in incoming.get(entry_id, []):
                from_file = _get_file_from_id(from_id)
                role = classify_path_role(from_file, policy) if from_file else "normal"

                if role == "exclude":
                    continue

                relation_evidence.append({
                    "from": from_id,
                    "to": entry_id,
                    "edge_type": etype,
                    "direction": "incoming",
                })

                if role == "reference_only":
                    cand["evidence"]["tests"].append(from_id)

        cand["evidence"]["relations"] = relation_evidence

    return candidates

def _discover_component_root_candidates(
    anchors: dict,
    file_anchor_index: dict,
    outgoing: dict,
    incoming: dict,
    dispatch_targets: set,
    policy: PathPolicy,
    existing_files: set,
) -> list:
    """发现尚未被高层锚点覆盖的组件根候选。

    对于每个尚未被覆盖的 normal 源文件，
    如果它有一个主类，把该类提升为低优先级候选。
    """
    candidates = []

    for fpath, file_anchors in file_anchor_index.items():
        role = classify_path_role(fpath, policy)
        if role != "normal":
            continue
        if fpath in existing_files:
            continue

        # 找主类
        classes = [a for a in file_anchors if _anchor_attr(a, "symbol_type") == "class"]
        if len(classes) == 1:
            cls = classes[0]
            cls_id = _anchor_attr(cls, "id")

            # 检查这个类是否有一定的关系边
            fanout = _count_call_fanout(cls_id, outgoing)
            fanin = _count_call_fanin(cls_id, incoming)
            if fanout + fanin >= 2:
                seed = build_candidate_seed(
                    cls_id, cls, "component_root",
                    ["single_class_file", f"edges({fanout}+{fanin})"],
                    policy,
                )
                candidates.append(seed)

    return candidates

def build_capability_candidates(
    root: str = ".",
    policy: Optional[PathPolicy] = None,
    anchors: Optional[dict] = None,
    relations: Optional[dict] = None,
) -> dict:
    """构建能力候选集。

    Args:
        root: 项目根目录
        policy: 路径策略（为 None 时自动加载）
        anchors: 锚点字典（为 None 时自动加载）
        relations: 关系字典（为 None 时自动加载）

    Returns:
        { "version": ..., "candidates": [...], "summary": {...} }
    """
    # ── 加载依赖 ──
    if policy is None:
        policy = load_path_policy(root)

    if anchors is None:
        from index.api.anchors import load_anchors
        anchors = load_anchors(root)

    if relations is None:
        from relate.api.relations import load_relations
        relations = load_relations(root)

    # ── 构建索引 ──
    outgoing, incoming, dispatch_targets = _build_edge_indexes(relations)
    file_anchor_index = _build_file_anchor_index(anchors)

    # ── 阶段 1：高层锚点候选 ──
    candidates = []
    covered_files = set()

    for symbol_id, anchor in anchors.items():
        fpath = _anchor_attr(anchor, "file", "")
        role = classify_path_role(fpath, policy)
        if _anchor_attr(anchor, "symbol_type", "") == "virtual_block" or _anchor_attr(anchor, "is_virtual", False):
            continue

        # exclude 完全跳过
        if role == "exclude":
            continue
        # reference_only 不能成为主候选
        if role == "reference_only":
            continue

        # 判定高层 / 低层
        is_high, source_type, signals = detect_high_level_anchor(
            symbol_id, anchor, outgoing, incoming,
            dispatch_targets, file_anchor_index, policy,
        )

        if is_high:
            seed = build_candidate_seed(
                symbol_id, anchor, source_type, signals, policy,
            )
            candidates.append(seed)
            covered_files.add(fpath)

    # ── 阶段 2：补充组件根候选 ──
    component_roots = _discover_component_root_candidates(
        anchors, file_anchor_index, outgoing, incoming,
        dispatch_targets, policy, covered_files,
    )
    candidates.extend(component_roots)

    # ── 阶段 3：挂载证据 ──
    candidates = attach_relation_evidence(
        candidates, anchors, outgoing, incoming, policy,
    )
    candidates = attach_reference_evidence(
        candidates, anchors, incoming, policy,
    )

    # ── 阶段 4：打分并排序 ──
    for cand in candidates:
        score_candidate(cand)

    candidates.sort(key=lambda c: c["score"], reverse=True)

    # ── 构建输出 ──
    summary = {
        "total_anchors": len(anchors),
        "total_candidates": len(candidates),
        "high_level_candidates": sum(
            1 for c in candidates
            if c["source_type"] in ("external_entry", "registry", "orchestrator")
        ),
        "component_root_candidates": sum(
            1 for c in candidates if c["source_type"] == "component_root"
        ),
        "area_candidates": sum(
            1 for c in candidates if c["source_type"] == "area"
        ),
        "covered_files": len(covered_files),
        "total_source_files": len(file_anchor_index),
    }

    result = {
        "version": "capability_candidates_v1",
        "root": str(Path(root).resolve()),
        "summary": summary,
        "candidates": candidates,
    }

    return result

def save_capability_candidates(data: dict, root: str = ".") -> str:
    """保存候选结果到 .codedendrite/capability_candidates.json。"""
    out_dir = Path(root) / ".codedendrite"
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "capability_candidates.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return str(out_path)

if __name__ == "__main__":
    import sys

    root = sys.argv[1] if len(sys.argv) > 1 else "."
    result = build_capability_candidates(root)

    print(f"=== 能力候选摘要 ===")
    for k, v in result["summary"].items():
        print(f"  {k}: {v}")

    print(f"\n=== Top 20 候选 ===")
    for c in result["candidates"][:20]:
        print(f"  [{c['score']:2d}] {c['source_type']:18s} {c['name_candidate']}")
        print(f"       area={c['area']}  files={len(c['files'])}  "
              f"symbols={len(c['symbols'])}  signals={c['signals']}")

    # 保存
    path = save_capability_candidates(result, root)
    print(f"\n保存到: {path}")
