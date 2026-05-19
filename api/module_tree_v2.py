"""
模块树 V2 生成器
========================
从 capability_candidates 合并生成项目级功能块导览图。

核心流程:
  candidates → module kernels → merge → 四格填充 → status/confidence → edges → completeness

用法:
    from api.module_tree_v2 import generate_module_tree_v2

    tree = generate_module_tree_v2("/path/to/project")
    # -> { "version": "module_tree_v2", "modules": [...], ... }
"""

import json
from collections import defaultdict
from pathlib import Path
from typing import Optional

from api.path_policy import (
    PathPolicy,
    classify_path_role,
    load_path_policy,
)
from api.capability_candidates import (
    build_capability_candidates,
    _build_edge_indexes,
    _anchor_attr,
)


# ── 模块核生成 ──────────────────────────────────────────────────

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


# ── 模块合并 ────────────────────────────────────────────────────

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


# ── 四格填充 ────────────────────────────────────────────────────

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


# ── 模块命名 ────────────────────────────────────────────────────

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


# ── Status 判定 ─────────────────────────────────────────────────

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


# ── Confidence 判定 ─────────────────────────────────────────────

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


# ── 模块间边 ────────────────────────────────────────────────────

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


# ── Completeness Report ─────────────────────────────────────────

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


# ── 清理临时字段 ────────────────────────────────────────────────

def _clean_module(module: dict) -> dict:
    """移除临时字段，输出干净的模块结构。"""
    clean = {k: v for k, v in module.items() if not k.startswith("_")}
    return clean


# ── 工具函数 ────────────────────────────────────────────────────

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


# ── 主入口 ──────────────────────────────────────────────────────

def generate_module_tree_v2(
    root: str = ".",
    policy: Optional[PathPolicy] = None,
    candidates: Optional[dict] = None,
    anchors: Optional[dict] = None,
    relations: Optional[dict] = None,
) -> dict:
    """生成 Module Tree V2。

    Args:
        root: 项目根目录
        policy: 路径策略
        candidates: 候选结果（build_capability_candidates 的输出）
        anchors: 锚点字典
        relations: 关系字典

    Returns:
        完整的模块树 JSON 结构
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

    if candidates is None:
        candidates = build_capability_candidates(root, policy, anchors, relations)

    cand_list = candidates.get("candidates", []) if isinstance(candidates, dict) else candidates

    # ── 1. 生成模块核 ──
    modules = build_module_kernels(cand_list, anchors, relations, policy)

    # ── 2. 合并 ──
    modules = merge_module_candidates(modules, relations, policy)

    # ── 3. 填充四格 + 命名 + status + confidence ──
    for mod in modules:
        fill_module_slots(mod)
        assign_module_name(mod)
        assign_module_status(mod)
        assign_module_confidence(mod)

    # ── 4. 按 status 优先级排序 ──
    status_order = {
        "core_flow": 0,
        "independent_capability": 1,
        "support_utility": 2,
        "dormant": 3,
        "uncertain": 4,
    }
    modules.sort(key=lambda m: (status_order.get(m["status"], 9), -m.get("_seed_score", 0)))

    # ── 5. 模块间边 ──
    edges = build_module_edges(modules, relations)

    # ── 6. 构建摘要 ──
    by_status = defaultdict(int)
    by_confidence = defaultdict(int)
    for mod in modules:
        by_status[mod["status"]] += 1
        by_confidence[mod["confidence"]] += 1

    # ── 7. 完整性报告 ──
    tree = {
        "version": "module_tree_v2",
        "root": str(Path(root).resolve()),
        "modules": modules,
        "edges": edges,
        "summary": {
            "total_modules": len(modules),
            "by_status": dict(by_status),
            "by_confidence": dict(by_confidence),
        },
    }

    completeness = build_completeness_report(tree, anchors, policy)
    tree["completeness"] = completeness

    # ── 8. 清理临时字段 ──
    tree["modules"] = [_clean_module(m) for m in modules]

    return tree


def save_module_tree_v2(tree: dict, root: str = ".") -> tuple:
    """保存模块树和完整性报告。

    Returns:
        (module_tree_path, completeness_path)
    """
    out_dir = Path(root) / ".codedendrite"
    out_dir.mkdir(parents=True, exist_ok=True)

    tree_path = out_dir / "module_tree_v2.json"
    with open(tree_path, "w", encoding="utf-8") as f:
        json.dump(tree, f, indent=2, ensure_ascii=False)

    # 单独保存 completeness
    comp_path = out_dir / "module_tree_v2_completeness.json"
    with open(comp_path, "w", encoding="utf-8") as f:
        json.dump(tree.get("completeness", {}), f, indent=2, ensure_ascii=False)

    return str(tree_path), str(comp_path)


# ── 主入口（直接运行时的快速测试）────────────────────────────────

if __name__ == "__main__":
    import sys

    root = sys.argv[1] if len(sys.argv) > 1 else "."
    tree = generate_module_tree_v2(root)

    print(f"=== Module Tree V2 ===")
    print(f"模块数: {tree['summary']['total_modules']}")
    print(f"状态分布: {tree['summary']['by_status']}")
    print(f"信心分布: {tree['summary']['by_confidence']}")
    print(f"模块间边: {len(tree['edges'])}")

    print(f"\n=== 模块列表 ===")
    for mod in tree["modules"]:
        print(f"  [{mod['confidence']}] {mod['status']:24s} {mod['name']}")
        print(f"      what: {mod['what'][:60]}")
        print(f"      files: {len(mod['files'])}  entries: {len(mod['entrypoints'])}")

    comp = tree.get("completeness", {})
    ac = comp.get("area_coverage", {})
    print(f"\n=== 完整性 ===")
    print(f"  区域覆盖: {ac.get('covered', 0)}/{ac.get('total_areas', 0)}")
    if ac.get("uncovered"):
        print(f"  未覆盖: {ac['uncovered']}")
    print(f"  假模块警告: {len(comp.get('fake_module_warnings', []))}")
    print(f"  低信心模块: {len(comp.get('low_confidence_modules', []))}")
    print(f"  证据不足: {len(comp.get('missing_evidence', []))}")

    # 保存
    tp, cp = save_module_tree_v2(tree, root)
    print(f"\n保存到: {tp}")
    print(f"完整性: {cp}")
