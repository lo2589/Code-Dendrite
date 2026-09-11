"""
模块树 V2 生成器
========================
从 capability_candidates 合并生成项目级功能块导览图。

核心流程:
  candidates → module kernels → merge → 四格填充 → status/confidence → edges → completeness

用法:
    from synth.api.module_tree_v2 import generate_module_tree_v2

    tree = generate_module_tree_v2("/path/to/project")
    # -> { "version": "module_tree_v2", "modules": [...], ... }
"""

import json
from collections import defaultdict
from pathlib import Path
from typing import Optional

from synth.api.path_policy import (
    PathPolicy,
    classify_path_role,
    load_path_policy,
)
from synth.api.capability_candidates import (
    build_capability_candidates,
    _build_edge_indexes,
    _anchor_attr,
)


# ── 模块核生成 ──────────────────────────────────────────────────

def _attach_supplements_to_modules(supplements: list, modules: list):
    """将低分补充候选挂载到最匹配的模块。"""
    for supp in supplements:
        best_module = None
        best_overlap = 0
        supp_files = set(supp.get("files", []))

        for mod in modules:
            mod_files = set(mod.get("files", []))
            overlap = len(supp_files & mod_files)
            if overlap > best_overlap:
                best_overlap = overlap
                best_module = mod

        if best_module is None and modules:
            # 默认挂到第一个
            best_module = modules[0]

        if best_module:
            for f in supp.get("files", []):
                if f not in best_module["files"]:
                    best_module["files"].append(f)
            for s in supp.get("symbols", []):
                if s not in best_module["_symbols"]:
                    best_module["_symbols"].append(s)
            for t in supp.get("evidence", {}).get("tests", []):
                if t not in best_module["evidence"]["tests"]:
                    best_module["evidence"]["tests"].append(t)

def _clean_module(module: dict) -> dict:
    """移除临时字段，输出干净的模块结构。"""
    clean = {k: v for k, v in module.items() if not k.startswith("_")}
    return clean

def _compute_merge_score(mod_a: dict, mod_b: dict, outgoing: dict) -> int:
    """计算两个模块的合并分数。"""
    score = 0

    # 1. 共享 area
    if mod_a.get("_area") and mod_a["_area"] == mod_b.get("_area"):
        score += 1

    # 2. 文件重叠
    files_a = set(mod_a.get("files", []))
    files_b = set(mod_b.get("files", []))
    if files_a and files_b:
        overlap = len(files_a & files_b)
        min_size = min(len(files_a), len(files_b))
        if min_size > 0 and overlap / min_size >= 0.5:
            score += 2

    # 3. 符号间边密度
    symbols_a = set(mod_a.get("_symbols", []))
    symbols_b = set(mod_b.get("_symbols", []))
    cross_edges = 0
    for sym in symbols_a:
        for to_id, _ in outgoing.get(sym, []):
            if to_id in symbols_b:
                cross_edges += 1
    for sym in symbols_b:
        for to_id, _ in outgoing.get(sym, []):
            if to_id in symbols_a:
                cross_edges += 1
    if cross_edges >= 3:
        score += 2
    elif cross_edges >= 1:
        score += 1

    return score

def _dedup(lst: list) -> list:
    """列表去重，保持顺序。"""
    seen = set()
    result = []
    for item in lst:
        key = json.dumps(item) if isinstance(item, dict) else item
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result

def _create_area_module(area: str, cands: list, counter: int) -> dict:
    """从同一 area 的多个低分候选合并创建区域模块。"""
    all_files = []
    all_symbols = []
    all_entries = []
    all_classes = []
    all_tests = []
    all_relations = []

    for c in cands:
        all_files.extend(c.get("files", []))
        all_symbols.extend(c.get("symbols", []))
        all_entries.extend(c.get("entrypoints", []))
        all_classes.extend(c.get("classes", []))
        all_tests.extend(c.get("evidence", {}).get("tests", []))
        all_relations.extend(c.get("evidence", {}).get("relations", []))

    return {
        "id": f"mod_{counter:03d}",
        "name": area,
        "status": "uncertain",
        "confidence": "D",
        "what": "",
        "how": "",
        "functions": [],
        "role": "",
        "entrypoints": _dedup(all_entries),
        "files": _dedup(all_files),
        "evidence": {
            "directories": [area],
            "entrypoints": _dedup(all_entries),
            "classes": _dedup(all_classes),
            "tests": _dedup(all_tests),
            "docs": [],
            "relations": all_relations[:20],
        },
        "risks": [],
        "_area": area,
        "_symbols": _dedup(all_symbols),
        "_source_type": "area",
        "_seed_score": max((c.get("score", 0) for c in cands), default=0),
        "_signals": [],
    }

def _create_module_from_seed(seed: dict, counter: int) -> dict:
    """从单个种子候选创建模块核。"""
    return {
        "id": f"mod_{counter:03d}",
        "name": seed.get("name_candidate", "unknown"),
        "status": "uncertain",
        "confidence": "D",
        "what": "",
        "how": "",
        "functions": [],
        "role": "",
        "entrypoints": list(seed.get("entrypoints", [])),
        "files": list(seed.get("files", [])),
        "evidence": {
            "directories": list(seed.get("evidence", {}).get("directories", [])),
            "entrypoints": list(seed.get("entrypoints", [])),
            "classes": list(seed.get("classes", [])),
            "tests": list(seed.get("evidence", {}).get("tests", [])),
            "docs": list(seed.get("evidence", {}).get("docs", [])),
            "relations": list(seed.get("evidence", {}).get("relations", [])),
        },
        "risks": [],
        # 临时字段，最终输出时移除
        "_area": seed.get("area", ""),
        "_symbols": list(seed.get("symbols", [])),
        "_source_type": seed.get("source_type", ""),
        "_seed_score": seed.get("score", 0),
        "_signals": list(seed.get("signals", [])),
    }

def _detect_fake_module(module: dict) -> bool:
    """检测可能的假模块。"""
    entries = module.get("entrypoints", [])
    files = module.get("files", [])
    symbols = module.get("_symbols", [])

    # 没有入口且只有 1 个文件
    if not entries and len(files) <= 1:
        return True

    # 只有 1 个符号
    if len(symbols) <= 1 and not entries:
        return True

    return False

def _merge_modules(target: dict, source: dict):
    """将 source 模块合并到 target。"""
    for f in source.get("files", []):
        if f not in target["files"]:
            target["files"].append(f)
    for s in source.get("_symbols", []):
        if s not in target["_symbols"]:
            target["_symbols"].append(s)
    for e in source.get("entrypoints", []):
        if e not in target["entrypoints"]:
            target["entrypoints"].append(e)

    # 合并证据
    for key in ("classes", "tests", "docs"):
        src_list = source.get("evidence", {}).get(key, [])
        tgt_list = target["evidence"].setdefault(key, [])
        for item in src_list:
            if item not in tgt_list:
                tgt_list.append(item)

    # 如果 source 分数更高，用它的名字
    if source.get("_seed_score", 0) > target.get("_seed_score", 0):
        target["name"] = source["name"]
        target["_seed_score"] = source["_seed_score"]

def assign_module_confidence(module: dict) -> str:
    """判定模块 confidence。

    A: >= 4 类证据
    B: >= 3 类证据
    C: 2 类证据
    D: < 2 类证据
    """
    evidence = module.get("evidence", {})

    types_present = 0
    if evidence.get("directories"):
        types_present += 1
    if evidence.get("entrypoints"):
        types_present += 1
    if evidence.get("classes"):
        types_present += 1
    if evidence.get("relations"):
        types_present += 1
    if evidence.get("tests") or evidence.get("docs"):
        types_present += 1

    if types_present >= 4:
        confidence = "A"
    elif types_present >= 3:
        confidence = "B"
    elif types_present >= 2:
        confidence = "C"
    else:
        confidence = "D"

    # fake module 降级
    if _detect_fake_module(module):
        confidence = min(confidence, "C", key=lambda x: ord(x))
        module["risks"].append("possible_fake_module")

    module["confidence"] = confidence
    return confidence

def assign_module_name(module: dict) -> str:
    """按优先级规则分配模块名。

    优先级: registry/entry label > class name > area label > function name
    """
    name = module.get("name", "")
    entries = module.get("entrypoints", [])
    classes = module.get("evidence", {}).get("classes", [])
    area = module.get("_area", "")

    # 如果当前名字包含 :: ，提取更短的可读名
    if "::" in name:
        parts = name.split("::")
        # 如果文件名和函数名不同，用 "文件名.函数名" 格式
        name = f"{parts[0]}.{parts[1]}" if len(parts) >= 2 else name

    # 如果名字太长或太技术化，尝试用 area
    if len(name) > 40 and area:
        name = area

    module["name"] = name
    return name

def assign_module_status(module: dict) -> str:
    """判定模块 status。"""
    entries = module.get("entrypoints", [])
    evidence = module.get("evidence", {})
    signals = module.get("_signals", [])
    score = module.get("_seed_score", 0)
    files = module.get("files", [])

    # 有入口 + 证据充分 → core_flow
    has_entries = len(entries) > 0
    has_relations = len(evidence.get("relations", [])) > 0
    has_tests = len(evidence.get("tests", [])) > 0
    has_classes = len(evidence.get("classes", [])) > 0

    evidence_count = sum([
        has_entries, has_relations, has_tests, has_classes,
        len(evidence.get("directories", [])) > 0,
    ])

    if has_entries and evidence_count >= 3 and score >= 8:
        status = "core_flow"
    elif has_entries and evidence_count >= 2:
        status = "independent_capability"
    elif evidence_count >= 2:
        status = "support_utility"
    elif len(files) >= 2:
        status = "dormant"
    else:
        status = "uncertain"

    module["status"] = status
    return status
