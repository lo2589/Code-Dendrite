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

def get_upward_chain(
    symbol: str,
    root: str = ".",
    max_depth: int = 6,
) -> List[dict]:
    """
    从 symbol 出发，沿 callers 方向往上追，返回整条上行调用树。
    每层取所有 callers（不只取一个），按父子路径展开。
    虚拟块 caller 自动透传到真实父函数。

    同一入口可以经不同调用者重复出现；只在当前路径内防环。

    Returns:
        [
          {"symbol": "Session.get_adapter", "file": "sessions.py", "line": 802, "depth": 0},
          {"symbol": "Session.send",        "file": "sessions.py", "line": 703, "depth": 1},
          ...
        ]
        depth=0 是入口本身，depth 越大越往上。
    """
    from index.api.anchors import get_anchor, load_anchors
    from relate.api.relations import load_relations

    try:
        rels = load_relations(root)
        edges = rels.get("edges", [])
    except Exception:
        edges = []

    try:
        all_anchors = load_anchors(root)
    except Exception:
        all_anchors = {}

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
        anchor = get_anchor(anchor_id, root)
        if not anchor:
            return []
        norm_id = anchor.id.replace("\\", "/")
        seen: set = set()
        result = []
        for edge in edges:
            if edge.get("edge_type") not in ("call", "dataflow"):
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
        chain.append({**node, "depth": depth, "parent_id": parent_id})
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
    from index.api.anchors import load_anchors
    anchors = load_anchors(root)
    norm = file_path.replace("\\", "/")
    result = [
        {"symbol": a.symbol, "type": a.symbol_type, "line": a.line_start, "id": a.id}
        for a in anchors.values()
        if not a.is_virtual and norm in a.file.replace("\\", "/")
    ]
    return sorted(result, key=lambda x: x["line"])
