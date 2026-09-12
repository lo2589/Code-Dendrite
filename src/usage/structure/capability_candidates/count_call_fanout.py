"""
能力候选提取器
========================
从静态证据（锚点 + 关系 + 路径策略）中提取能力候选，
供 module_tree_v2.py 合并成最终模块。

能力候选 = 高层锚点 + 局部邻域证据 + 引用证据 + 打分

用法:
    from usage.structure.capability_candidates import build_capability_candidates

    result = build_capability_candidates("/path/to/project")
    # -> { "version": ..., "candidates": [...], "summary": {...} }
"""

import json
import os
from collections import defaultdict
from pathlib import Path
from typing import Optional

from usage.path_policy import (
    PathPolicy,
    classify_path_role,
    load_path_policy,
    normalize_project_path,
)


# ── 锚点适配（兼容 Anchor 对象和 dict）──────────────────────────

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

def _infer_area(file_path: str) -> str:
    """从文件路径推断所属区域。"""
    parts = file_path.split("/")
    if len(parts) >= 2:
        return parts[0]
    return ""

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

def _get_file_from_id(symbol_id: str) -> str:
    """从 symbol_id 提取文件路径。"""
    return symbol_id.split("::")[0] if "::" in symbol_id else ""

def _count_distinct_caller_files(symbol_id: str, incoming: dict) -> int:
    """计算调用者来自多少个不同文件。"""
    files = set()
    for fid, etype in incoming.get(symbol_id, []):
        if etype in ("call", "dispatch"):
            f = _get_file_from_id(fid)
            if f:
                files.add(f)
    return len(files)

def _count_call_fanout(symbol_id: str, outgoing: dict) -> int:
    """计算一个符号的 call 类型出边数量。"""
    return sum(1 for _, etype in outgoing.get(symbol_id, []) if etype == "call")

def _is_private_symbol(symbol_name: str) -> bool:
    """判断是否为私有符号（以 _ 开头但不是 __dunder__）。"""
    return symbol_name.startswith("_") and not symbol_name.startswith("__")

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

def _count_call_fanin(symbol_id: str, incoming: dict) -> int:
    """计算一个符号被 call 的入边数量。"""
    return sum(1 for _, etype in incoming.get(symbol_id, []) if etype == "call")
