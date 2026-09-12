"""
模块树 V2 生成器
========================
从 capability_candidates 合并生成项目级功能块导览图。

核心流程:
  candidates → module kernels → merge → 四格填充 → status/confidence → edges → completeness

用法:
    from usage.structure.module_tree_v2 import generate_module_tree_v2

    tree = generate_module_tree_v2("/path/to/project")
    # -> { "version": "module_tree_v2", "modules": [...], ... }
"""

import json
from collections import defaultdict
from pathlib import Path
from typing import Optional

from usage.path_policy import (
    PathPolicy,
    classify_path_role,
    load_path_policy,
)
from usage.structure.capability_candidates import (
    build_capability_candidates,
    _build_edge_indexes,
    _anchor_attr,
)


# ── 模块核生成 ──────────────────────────────────────────────────

from usage.structure.module_tree_v2.module_assign import _clean_module, assign_module_confidence, assign_module_name, assign_module_status
from usage.structure.module_tree_v2.module_completeness import build_completeness_report, build_module_edges, build_module_kernels, fill_module_slots, merge_module_candidates

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
        from analyzer.anchors import load_anchors
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
