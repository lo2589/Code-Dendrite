"""
模块树 V2：功能树
========================
一个模块就是一个功能：从入口（__main__、注册的函数、调用图的根）开始，顺着调用边走到的
代码就是它的实现；被多个功能共用的代码单独成"共享底座"。每个模块说清 what（入口的文档
字符串）和 how（入口按调用顺序走过的每一步）。算法见 feature_tree。

以前按"目录第一段 + 一条边就合并"生成，代码搬进 src/ 以后全仓库只剩一个目录，模块塌成
几个大杂烩，what/how 也只是模板句。

用法:
    from usage.structure.module_tree_v2 import generate_module_tree_v2

    tree = generate_module_tree_v2("/path/to/project")
    # -> { "version": "module_tree_v2", "modules": [...], "edges": [...], ... }
"""

import json
from pathlib import Path
from typing import Optional

from usage.path_policy import PathPolicy, load_path_policy
from usage.structure.module_tree_v2.feature_tree import build_feature_tree


def generate_module_tree_v2(
    root: str = ".",
    policy: Optional[PathPolicy] = None,
    candidates: Optional[dict] = None,
    anchors: Optional[dict] = None,
    relations: Optional[dict] = None,
) -> dict:
    """生成功能树。candidates / relations 只为兼容旧调用方保留，不再使用。"""
    if policy is None:
        policy = load_path_policy(root)
    if anchors is None:
        from analyzer.anchors import load_anchors
        anchors = load_anchors(root)
    tree = build_feature_tree(str(Path(root).resolve()), anchors, policy)
    tree["root"] = str(Path(root).resolve())
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
        print(f"  [{mod['confidence']}] {mod['status']:24s} {mod['name']}  ({mod['size']['functions']} 个函数)")
        print(f"      what: {mod['what'][:80]}")

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
