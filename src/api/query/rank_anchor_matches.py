"""
query.py — CodeDendrite 查询 CLI
================================
用法:
    python api/query.py edges <keyword>          # 过滤边
    python api/query.py count                    # 统计边类型
    python api/query.py expand <node_id>         # 展开节点
    python api/query.py anchors <keyword>        # 过滤锚点
    python api/query.py fileanchors <file>       # 列出单个文件内的 anchors
    python api/query.py graph [focus] [radius]   # 生成交互式关系图
    python api/query.py timeline <entry> [depth]  # 生成调用链时间线
    python api/query.py codemap                  # 生成代码地图
"""
import sys
import os

def _rank_anchor_matches(anchors, keyword: str):
    """Return symbol and path matches, with useful symbol matches first."""
    kw = keyword.strip().lower()
    ranked = []
    for aid, anchor in anchors.items():
        symbol = anchor.symbol if hasattr(anchor, "symbol") else anchor.get("symbol", "")
        path = anchor.file if hasattr(anchor, "file") else anchor.get("file", "")
        line = anchor.line_start if hasattr(anchor, "line_start") else anchor.get("line_start", 0)
        symbol_lower = symbol.lower()
        leaf = symbol_lower.rsplit(".", 1)[-1]
        path_lower = path.replace("\\", "/").lower()

        if symbol_lower == kw:
            rank = 0                   # top-level exact symbol
        elif leaf == kw:
            rank = 1                   # exact method/function leaf
        elif symbol_lower.startswith(kw):
            rank = 2
        elif leaf.startswith(kw):
            rank = 3
        elif kw in symbol_lower:
            rank = 4
        elif kw in path_lower:
            rank = 5                   # legacy file-path behaviour
        else:
            continue
        ranked.append(((rank, len(symbol_lower), path_lower, line or 0, aid), aid, anchor))
    ranked.sort(key=lambda item: item[0])
    return [(aid, anchor) for _, aid, anchor in ranked]
