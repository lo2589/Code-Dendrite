"""
inspector.py — 轻量代码导航接口

    list_file_anchors(file_path, root)   → 文件内所有函数/类列表
    find_anchor(keyword, root)           → 按函数名模糊搜索
    get_anchor_source(symbol, root)      → anchor 源码（上下各 +3 行）
    get_anchor_relations(symbol, root)   → 调用者 + 被调用者（一层），带跳转历史
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import List, Optional

# 上行链的基础节点阈值：被这么多不同 anchor 调用的东西是公共基础件，
# 从它往上追没有意义（详见 get_upward_chain 的 docstring）。
BASE_FAN_IN = 20

def get_upward_chain(
    symbol: str,
    root: str = ".",
    max_depth: int = 6,
    base_fan_in: int = BASE_FAN_IN,
) -> List[dict]:
    """
    从 symbol 出发，沿 callers 方向往上追，返回整条上行调用树。
    每层取所有 callers（不只取一个），按父子路径展开。
    虚拟块 caller 自动透传到真实父函数。

    同一入口可以经不同调用者重复出现；只在当前路径内防环。

    扇入（被多少个不同 anchor 调用）达到 base_fan_in 的节点视为**基础节点**：
    工具函数、公共类型这类几乎被所有东西调用的东西，从它再往上追没有意义，
    而且它的每个 caller 都会引出一整棵子树，结果集会按路径数炸开。这类节点
    照常出现在结果里，但标上 is_base / stop 说明为什么到此为止，不再往下展开。

    Args:
        base_fan_in: 基础节点判定阈值。本仓库实测扇入分布——>=20 的只有 70 个
            节点（2.7%），>=50 的 5 个；调小会裁得更狠，调大则保留更多上行层。

    Returns:
        [
          {"symbol": "Session.send", "file": "sessions.py", "line": 703,
           "depth": 1, "parent_id": "...", "caller_count": 4},
          {"symbol": "load_anchors", "file": "core_load.py", "line": 33,
           "depth": 2, "parent_id": "...", "caller_count": 102,
           "is_base": True, "stop": "base_node"},
          ...
        ]
        depth=0 是入口本身，depth 越大越往上。
        caller_count 是被多少个不同 anchor 调用；
        is_base=True 表示这是基础节点、已停止继续上行。
    """
    from analyzer.anchors import get_anchor, load_anchors
    from api.relations import load_relations

    try:
        rels = load_relations(root)
        edges = rels.get("edges", [])
    except Exception:
        edges = []

    try:
        all_anchors = load_anchors(root)
    except Exception:
        all_anchors = {}

    # 扇入表：每个 to_id 被哪些不同的 anchor 调用过。一次 O(E) 扫完，
    # 供 visit() 判定基础节点用。
    caller_ids: dict = {}
    for edge in edges:
        if edge.get("edge_type") not in ("call", "dispatch"):
            continue
        to_id = edge.get("to_id", "").replace("\\", "/")
        from_id = edge.get("from_id", "").replace("\\", "/")
        if to_id and from_id:
            caller_ids.setdefault(to_id, set()).add(from_id)

    def caller_count(anchor_id: str) -> int:
        return len(caller_ids.get(anchor_id.replace("\\", "/"), ()))

    def _vblock_real_parent(vblock_id: str):
        visited_vb: set = set()
        cur_id = vblock_id
        while cur_id and cur_id not in visited_vb:
            visited_vb.add(cur_id)
            cur = all_anchors.get(cur_id) or all_anchors.get(cur_id.replace("\\", "/"))
            if not cur:
                break
            if not cur.is_virtual:
                return cur
            cur_id = getattr(cur, "parent_anchor", None) or ""
        return None

    def callers_of(anchor_id: str) -> List[dict]:
        # 与 callees_of 同款：先查已经加载好的 all_anchors，只有查不到才回落到
        # get_anchor()。get_anchor 每次都重解析一遍 anchors.json（无缓存，实测
        # 单次 ~74ms），逐条边调用会把上行遍历拖成分钟级。
        anchor = all_anchors.get(anchor_id) or all_anchors.get(anchor_id.replace("\\", "/"))
        if anchor is None:
            anchor = get_anchor(anchor_id, root)
        if not anchor:
            return []
        norm_id = anchor.id.replace("\\", "/")
        seen: set = set()
        result = []
        for edge in edges:
            if edge.get("edge_type") not in ("call", "dispatch"):
                continue
            if edge.get("to_id", "").replace("\\", "/") != norm_id:
                continue
            from_id = edge.get("from_id", "").replace("\\", "/")
            if "#" in from_id:
                real = _vblock_real_parent(from_id)
                if not real:
                    continue
                key = real.id.replace("\\", "/")
                if key in seen:
                    continue
                seen.add(key)
                result.append({
                    "id": real.id,
                    "symbol": real.symbol,
                    "file": real.file,
                    "line": real.line_start,
                })
            else:
                if from_id in seen:
                    continue
                seen.add(from_id)
                raw_from_id = edge.get("from_id", "")
                caller_anchor = all_anchors.get(from_id) or all_anchors.get(raw_from_id)
                if caller_anchor is None and ("::" in from_id or "#" in from_id):
                    caller_anchor = get_anchor(from_id, root)
                if caller_anchor and not caller_anchor.is_virtual:
                    result.append({
                        "id": caller_anchor.id,
                        "symbol": caller_anchor.symbol,
                        "file": caller_anchor.file,
                        "line": caller_anchor.line_start,
                    })
        return result

    entry_anchor = get_anchor(symbol, root)
    if entry_anchor:
        entry = {
            "id": entry_anchor.id,
            "symbol": entry_anchor.symbol,
            "file": entry_anchor.file,
            "line": entry_anchor.line_start,
        }
    else:
        entry = {"id": symbol, "symbol": symbol, "file": None, "line": None}

    chain: List[dict] = []

    def visit(node: dict, depth: int, path: tuple, parent_id: Optional[str]) -> None:
        node_id = node["id"]
        count = caller_count(node_id)
        row = {**node, "depth": depth, "parent_id": parent_id, "caller_count": count}

        # 基础节点：被足够多的东西调用，说明它是公共底座而不是某条业务链的
        # 中间环节。标出来停住——再往上每个 caller 都会引出一整棵子树，
        # 而那一层信息对「这东西被谁用」没有增量。
        if count >= base_fan_in:
            row["is_base"] = True
            row["stop"] = "base_node"
            chain.append(row)
            return

        chain.append(row)
        if depth >= max_depth:
            return
        next_path = path + (node_id,)
        for caller in callers_of(node_id):
            if caller["id"] in next_path:
                continue
            visit(caller, depth + 1, next_path, node_id)

    visit(entry, 0, (), None)

    return chain

def list_file_anchors(file_path: str, root: str = ".") -> List[dict]:
    """
    列出文件内所有真实 anchor（排除 virtual block）。

    Returns:
        [{symbol, type, line, id}]，按行号排序
    """
    from analyzer.anchors import load_anchors
    anchors = load_anchors(root)
    norm = file_path.replace("\\", "/")
    result = [
        {"symbol": a.symbol, "type": a.symbol_type, "line": a.line_start, "id": a.id}
        for a in anchors.values()
        if not a.is_virtual and norm in a.file.replace("\\", "/")
    ]
    return sorted(result, key=lambda x: x["line"])
