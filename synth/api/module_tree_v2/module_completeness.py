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

from synth.api.module_tree_v2.module_assign import _attach_supplements_to_modules, _compute_merge_score, _create_area_module, _create_module_from_seed, _merge_modules

def build_completeness_report(
    tree: dict,
    anchors: dict,
    policy: PathPolicy,
) -> dict:
    """生成完整性报告。"""
    modules = tree.get("modules", [])

    # 1. 区域覆盖
    all_areas = set()
    covered_areas = set()
    for _, anchor in anchors.items():
        fpath = _anchor_attr(anchor, "file", "")
        role = classify_path_role(fpath, policy)
        if role == "normal":
            parts = fpath.split("/")
            if len(parts) >= 2:
                all_areas.add(parts[0])

    for mod in modules:
        area = mod.get("_area", "")
        if area:
            covered_areas.add(area)

    uncovered = sorted(all_areas - covered_areas)

    # 2. 假模块警告
    fake_warnings = []
    for mod in modules:
        if "possible_fake_module" in mod.get("risks", []):
            fake_warnings.append({
                "module_id": mod["id"],
                "name": mod["name"],
                "reason": "缺少入口或符号过少",
            })

    # 3. 低 confidence 模块
    low_confidence = []
    for mod in modules:
        if mod.get("confidence") in ("C", "D"):
            low_confidence.append({
                "module_id": mod["id"],
                "name": mod["name"],
                "confidence": mod["confidence"],
            })

    # 4. 证据不足
    missing_evidence = []
    for mod in modules:
        evidence = mod.get("evidence", {})
        missing = []
        if not evidence.get("entrypoints"):
            missing.append("entrypoints")
        if not evidence.get("classes"):
            missing.append("classes")
        if not evidence.get("relations"):
            missing.append("relations")
        if not evidence.get("tests"):
            missing.append("tests")
        if len(missing) >= 3:
            missing_evidence.append({
                "module_id": mod["id"],
                "name": mod["name"],
                "missing": missing,
            })

    return {
        "area_coverage": {
            "total_areas": len(all_areas),
            "covered": len(covered_areas),
            "uncovered": uncovered,
        },
        "fake_module_warnings": fake_warnings,
        "low_confidence_modules": low_confidence,
        "missing_evidence": missing_evidence,
    }

def build_module_edges(modules: list, relations: dict) -> list:
    """构建模块间的依赖边。"""
    outgoing, _, _ = _build_edge_indexes(relations)

    # 建立 symbol -> module 映射
    sym_to_mod = {}
    for mod in modules:
        for sym in mod.get("_symbols", []):
            sym_to_mod[sym] = mod["id"]
        for ep in mod.get("entrypoints", []):
            sym_to_mod[ep] = mod["id"]

    # 统计模块间边
    edge_counter = defaultdict(lambda: defaultdict(int))

    for mod in modules:
        mod_id = mod["id"]
        for sym in mod.get("_symbols", []) + mod.get("entrypoints", []):
            for to_id, etype in outgoing.get(sym, []):
                to_mod = sym_to_mod.get(to_id)
                if to_mod and to_mod != mod_id:
                    edge_counter[(mod_id, to_mod)][etype] += 1

    edges = []
    for (from_mod, to_mod), type_counts in edge_counter.items():
        total = sum(type_counts.values())
        dominant_type = max(type_counts, key=type_counts.get)
        edges.append({
            "from": from_mod,
            "to": to_mod,
            "edge_type": dominant_type,
            "weight": total,
        })

    return edges

def build_module_kernels(
    candidates: list,
    anchors: dict,
    relations: dict,
    policy: PathPolicy,
) -> list:
    """从候选生成初始模块核。

    策略: 按 area 分组，同一 area 内的高分候选作为核心，
    低分候选降级为补充证据。
    """
    # 按 area 分组
    area_groups = defaultdict(list)
    no_area = []

    for cand in candidates:
        area = cand.get("area", "")
        if area:
            area_groups[area].append(cand)
        else:
            no_area.append(cand)

    modules = []
    mod_counter = 0

    # 每个 area 生成一个或多个模块
    for area, cands in sorted(area_groups.items()):
        # 按 score 降序
        cands.sort(key=lambda c: c.get("score", 0), reverse=True)

        # 区分高分种子和低分补充
        seeds = [c for c in cands if c.get("score", 0) >= 5]
        supplements = [c for c in cands if c.get("score", 0) < 5]

        if not seeds:
            # 没有高分种子，取最高分的作为核心
            if cands:
                seeds = [cands[0]]
                supplements = cands[1:]

        # 每个高分种子单独成核
        for seed in seeds:
            mod_counter += 1
            module = _create_module_from_seed(seed, mod_counter)
            modules.append(module)

        # 低分补充：检查是否应该挂载到已有模块还是合并成一个 area 模块
        if supplements and not seeds:
            mod_counter += 1
            module = _create_area_module(area, supplements, mod_counter)
            modules.append(module)
        elif supplements:
            # 挂到最近的种子模块
            _attach_supplements_to_modules(supplements, modules[-len(seeds):])

    # 无 area 候选单独处理
    for cand in no_area:
        if cand.get("score", 0) >= 5:
            mod_counter += 1
            module = _create_module_from_seed(cand, mod_counter)
            modules.append(module)

    return modules

def fill_module_slots(module: dict) -> dict:
    """填充 what / how / functions / role。"""
    area = module.get("_area", "")
    name = module.get("name", "")
    entries = module.get("entrypoints", [])
    files = module.get("files", [])
    symbols = module.get("_symbols", [])
    classes = module.get("evidence", {}).get("classes", [])

    # what: 基于入口和类推断
    if entries:
        entry_names = [e.split("::")[-1] if "::" in e else e for e in entries[:3]]
        module["what"] = f"提供 {', '.join(entry_names)} 等入口能力"
    elif classes:
        cls_names = [c.split("::")[-1] if "::" in c else c for c in classes[:3]]
        module["what"] = f"以 {', '.join(cls_names)} 为核心的组件"
    elif area:
        module["what"] = f"{area} 区域功能"
    else:
        module["what"] = "unknown"

    # how: 基于文件和关系推断
    if len(files) > 0:
        module["how"] = f"通过 {len(files)} 个文件实现，包含 {len(symbols)} 个符号"
    else:
        module["how"] = "to_verify"

    # functions: 列出关键入口和类
    funcs = []
    for e in entries[:5]:
        funcs.append(e)
    for c in classes[:3]:
        if c not in funcs:
            funcs.append(c)
    module["functions"] = funcs

    # role
    source_type = module.get("_source_type", "")
    if source_type in ("external_entry", "registry"):
        module["role"] = f"对外提供 {name} 能力"
    elif source_type == "orchestrator":
        module["role"] = f"编排协调 {area or name} 流程"
    elif area:
        module["role"] = f"{area} 区域的核心功能块"
    else:
        module["role"] = "to_verify"

    return module

def merge_module_candidates(
    modules: list,
    relations: dict,
    policy: PathPolicy,
) -> list:
    """合并共享结构关系的模块。

    合并条件（至少满足两类）:
    1. 共享 area
    2. 共享 files（>= 50% 重叠）
    3. 模块间有强边密度
    """
    if len(modules) <= 1:
        return modules

    outgoing, incoming, _ = _build_edge_indexes(relations)

    # 建立模块间关系矩阵
    n = len(modules)
    merge_scores = [[0] * n for _ in range(n)]

    for i in range(n):
        for j in range(i + 1, n):
            score = _compute_merge_score(modules[i], modules[j], outgoing)
            merge_scores[i][j] = score
            merge_scores[j][i] = score

    # 贪心合并：从最高分开始
    merged = [False] * n
    result = []

    while True:
        best_score = 0
        best_i, best_j = -1, -1
        for i in range(n):
            if merged[i]:
                continue
            for j in range(i + 1, n):
                if merged[j]:
                    continue
                if merge_scores[i][j] > best_score:
                    best_score = merge_scores[i][j]
                    best_i, best_j = i, j

        if best_score < 2:
            break

        # 合并 j 到 i
        _merge_modules(modules[best_i], modules[best_j])
        merged[best_j] = True

    # 收集未被合并的
    for i in range(n):
        if not merged[i]:
            result.append(modules[i])

    return result
