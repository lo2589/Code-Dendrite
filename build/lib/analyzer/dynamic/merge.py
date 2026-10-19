"""
merge.py — 静态图融合动态数据（只读）

不修改原数据，返回 enriched copy。
新增字段：
  - observed_in_trace: bool
  - executed_count: int
  - last_seen: float
"""

from __future__ import annotations

import copy
from typing import Optional


def merge_static_with_executed(
    relations: list[dict],
    executed_edges: list[dict],
) -> list[dict]:
    """将动态执行数据融合到静态关系图。

    不修改原数据，返回 enriched copy。

    Args:
        relations: 静态关系边列表（from_id, to_id, edge_type...）
        executed_edges: 动态执行边列表（src, dst, count, last_seen）

    Returns:
        enriched 的静态边列表，每条边额外包含：
        - observed_in_trace: bool
        - executed_count: int (0 if not observed)
        - last_seen: float | None
    """
    # 构建动态边查找索引
    # key: "from_qualname -> to_qualname"
    exec_index: dict[str, dict] = {}
    for edge in executed_edges:
        src = edge.get("src", "")
        dst = edge.get("dst", "")
        key = f"{src} -> {dst}"
        exec_index[key] = edge

    enriched = []
    for rel in relations:
        r = copy.copy(rel)

        # 静态边的 from_id / to_id 格式: "file.py::func_name"
        # 动态边的 src / dst 格式: "qualname" (如 "Class.method")
        # 需要尝试多种匹配方式
        from_id = r.get("from_id", "")
        to_id = r.get("to_id", "")

        matched = _find_match(from_id, to_id, exec_index)

        if matched:
            r["observed_in_trace"] = True
            r["executed_count"] = matched.get("count", 0)
            r["last_seen"] = matched.get("last_seen")
        else:
            r["observed_in_trace"] = False
            r["executed_count"] = 0
            r["last_seen"] = None

        enriched.append(r)

    return enriched


def _find_match(
    from_id: str,
    to_id: str,
    exec_index: dict[str, dict],
) -> Optional[dict]:
    """尝试多种方式匹配静态边和动态边。

    静态边格式: "path/to/file.py::ClassName.method"
    动态边格式: "ClassName.method"

    匹配策略（按优先级）：
    1. 精确匹配 qualname 部分
    2. 末尾 qualname 匹配
    """
    # 提取 qualname 部分（:: 后面的部分）
    from_qual = from_id.split("::")[-1] if "::" in from_id else from_id
    to_qual = to_id.split("::")[-1] if "::" in to_id else to_id

    # 策略 1: 直接匹配
    key = f"{from_qual} -> {to_qual}"
    if key in exec_index:
        return exec_index[key]

    # 策略 2: 函数名匹配（去掉类前缀）
    from_func = from_qual.split(".")[-1]
    to_func = to_qual.split(".")[-1]

    for exec_key, exec_edge in exec_index.items():
        src = exec_edge.get("src", "")
        dst = exec_edge.get("dst", "")
        src_func = src.split(".")[-1]
        dst_func = dst.split(".")[-1]

        if src_func == from_func and dst_func == to_func:
            return exec_edge

    return None
