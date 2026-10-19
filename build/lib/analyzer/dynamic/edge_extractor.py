"""
edge_extractor.py — 从 trace 事件中提取执行边

将 trace_events.jsonl 中的 call 事件聚合为：
  caller_qualname → callee_qualname 的边 + 调用次数 + 最后出现时间
"""

from __future__ import annotations

from typing import Iterable


def build_edge_key(src: str, dst: str) -> str:
    """构建边的唯一键。"""
    return f"{src} -> {dst}"


def extract_executed_edges(events: Iterable[dict]) -> list[dict]:
    """从 trace 事件流中提取执行边。

    只处理 event=="call" 且有 caller_qualname 的事件。

    Returns:
        executed_edges.json 格式的列表：
        [{"src": "A.foo", "dst": "B.bar", "count": 3, "last_seen": 1710000000.123}]
    """
    edge_map: dict[str, dict] = {}

    for ev in events:
        if ev.get("event") != "call":
            continue

        caller = ev.get("caller_qualname")
        callee = ev.get("qualname")

        if not caller or not callee:
            continue

        # 跳过自调用
        if caller == callee:
            continue

        key = build_edge_key(caller, callee)

        if key in edge_map:
            edge_map[key]["count"] += 1
            edge_map[key]["last_seen"] = ev.get("ts", 0)
        else:
            edge_map[key] = {
                "src": caller,
                "dst": callee,
                "count": 1,
                "last_seen": ev.get("ts", 0),
            }

    # 按调用次数降序
    edges = sorted(edge_map.values(), key=lambda e: e["count"], reverse=True)
    return edges
