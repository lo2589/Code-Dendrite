"""
能力候选提取器
========================
从静态证据（锚点 + 关系 + 路径策略）中提取能力候选，
供 module_tree_v2.py 合并成最终模块。

能力候选 = 高层锚点 + 局部邻域证据 + 引用证据 + 打分

用法:
    from api.capability_candidates import build_capability_candidates

    result = build_capability_candidates("/path/to/project")
    # -> { "version": ..., "candidates": [...], "summary": {...} }
"""

import json
import os
from collections import defaultdict
from pathlib import Path
from typing import Optional

from api.path_policy import (
    PathPolicy,
    classify_path_role,
    load_path_policy,
    normalize_project_path,
)


# ── 锚点适配（兼容 Anchor 对象和 dict）──────────────────────────

def _anchor_attr(anchor, key: str, default=""):
    """从 Anchor 对象或 dict 中读取属性。"""
    if isinstance(anchor, dict):
        return anchor.get(key, default)
    return getattr(anchor, key, default)


# ── 边索引构建 ──────────────────────────────────────────────────

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


# ── 高层 / 低层锚点判定 ─────────────────────────────────────────

def _get_file_from_id(symbol_id: str) -> str:
    """从 symbol_id 提取文件路径。"""
    return symbol_id.split("::")[0] if "::" in symbol_id else ""


def _count_call_fanout(symbol_id: str, outgoing: dict) -> int:
    """计算一个符号的 call 类型出边数量。"""
    return sum(1 for _, etype in outgoing.get(symbol_id, []) if etype == "call")


def _count_call_fanin(symbol_id: str, incoming: dict) -> int:
    """计算一个符号被 call 的入边数量。"""
    return sum(1 for _, etype in incoming.get(symbol_id, []) if etype == "call")


def _count_distinct_caller_files(symbol_id: str, incoming: dict) -> int:
    """计算调用者来自多少个不同文件。"""
    files = set()
    for fid, etype in incoming.get(symbol_id, []):
        if etype in ("call", "dispatch"):
            f = _get_file_from_id(fid)
            if f:
                files.add(f)
    return len(files)


def _is_private_symbol(symbol_name: str) -> bool:
    """判断是否为私有符号（以 _ 开头但不是 __dunder__）。"""
    return symbol_name.startswith("_") and not symbol_name.startswith("__")


def _is_low_distinctiveness_name(symbol_name: str) -> bool:
    """判断是否为低区分度的通用方法名。

    这些名字在多个类中重复出现，不适合作为顶层候选名。
    规则基于结构模式（序列化/生命周期/工具方法），而非项目特例。
    """
    low_names = {
        # 序列化模式
        "from_dict", "to_dict", "from_json", "to_json",
        "serialize", "deserialize", "encode", "decode",
        # 生命周期模式
        "__init__", "__repr__", "__str__", "__eq__", "__hash__",
        "setup", "teardown", "close", "cleanup", "reset",
        # 通用工具模式
        "get", "set", "update", "delete", "execute", "run",
        "validate", "parse", "format", "convert",
        "load", "save", "read", "write",
    }
    return symbol_name in low_names


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


# ── 候选种子构建 ────────────────────────────────────────────────

def _infer_area(file_path: str) -> str:
    """从文件路径推断所属区域。"""
    parts = file_path.split("/")
    if len(parts) >= 2:
        return parts[0]
    return ""


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


# ── 证据挂载 ────────────────────────────────────────────────────

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


def attach_reference_evidence(
    candidates: list,
    anchors: dict,
    incoming: dict,
    policy: PathPolicy,
) -> list:
    """为每个候选挂载引用证据（被 reference_only 路径引用的记录）。"""
    for cand in candidates:
        ref_evidence = []
        for sym_id in cand["entrypoints"]:
            for from_id, etype in incoming.get(sym_id, []):
                from_file = _get_file_from_id(from_id)
                role = classify_path_role(from_file, policy) if from_file else "normal"
                if role == "reference_only":
                    ref_evidence.append({
                        "symbol": from_id,
                        "file": from_file,
                        "edge_type": etype,
                    })
        cand["evidence"]["references"] = ref_evidence

    return candidates


# ── 打分 ────────────────────────────────────────────────────────

def score_candidate(candidate: dict) -> int:
    """给候选打分。

    基于结构信号，不基于项目特例。
    """
    score = 0
    signals = candidate.get("signals", [])
    source_type = candidate.get("source_type", "")

    # ── 加分 ──
    # 外部入口 / 注册接口
    if source_type in ("external_entry", "registry"):
        score += 5
    # 编排器
    elif source_type == "orchestrator":
        score += 4
    # 组件根
    elif source_type == "component_root":
        score += 3

    # dispatch 目标额外加分
    if any("dispatch_target" in s for s in signals):
        score += 2

    # 多文件调用者
    for s in signals:
        if s.startswith("multi_file_callers"):
            score += 2
            break

    # 高 fanout
    for s in signals:
        if s.startswith("high_fanout"):
            score += 1
            break

    # 多类型证据（relations + tests）
    evidence = candidate.get("evidence", {})
    evidence_types = 0
    if evidence.get("relations"):
        evidence_types += 1
    if evidence.get("tests"):
        evidence_types += 1
    if evidence.get("references"):
        evidence_types += 1
    if evidence.get("docs"):
        evidence_types += 1
    if evidence_types >= 2:
        score += 2

    # 多文件覆盖
    if len(candidate.get("files", [])) >= 3:
        score += 1

    # ── 减分 ──
    notes = candidate.get("notes", [])
    if "low_semantic_name" in notes:
        score -= 4

    if not candidate.get("entrypoints"):
        score -= 3

    if candidate.get("policy") == "reference_only":
        score -= 2

    # 没有任何关系边证据
    if not evidence.get("relations"):
        score -= 1

    candidate["score"] = max(score, 0)
    return candidate["score"]


# ── 组件根候选发现（补充覆盖）─────────────────────────────────

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


# ── 主入口 ──────────────────────────────────────────────────────

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
        from api.anchors import load_anchors
        anchors = load_anchors(root)

    if relations is None:
        from api.relations import load_relations
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


# ── 主入口（直接运行时的快速测试）────────────────────────────────

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
