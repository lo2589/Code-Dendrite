"""
route_mapper.py — 从执行边中提取路由映射

识别分发器模式：
- src 名字包含 dispatch / route / handle_request / process
- 收集其所有 dst → 作为路由目标
"""

from __future__ import annotations

import re
from typing import Optional


# 分发器函数名模式
_DISPATCHER_PATTERNS = [
    re.compile(r"dispatch", re.IGNORECASE),
    re.compile(r"route", re.IGNORECASE),
    re.compile(r"handle_request", re.IGNORECASE),
    re.compile(r"process_message", re.IGNORECASE),
    re.compile(r"_handle_request", re.IGNORECASE),
]


def _is_dispatcher(qualname: str) -> bool:
    """判断一个函数是否是分发器。"""
    for pat in _DISPATCHER_PATTERNS:
        if pat.search(qualname):
            return True
    return False


def extract_dispatch_routes(
    edges: list[dict],
    custom_dispatchers: Optional[list[str]] = None,
) -> dict:
    """从执行边中提取路由映射。

    Args:
        edges: executed_edges.json 格式的列表
        custom_dispatchers: 自定义分发器名称列表

    Returns:
        routes.json 格式：
        {
            "dispatch_routes": [
                {
                    "dispatcher": "Server._handle_request",
                    "targets": ["_handle_chat_with_model", "_handle_stop_all", ...]
                }
            ]
        }
    """
    # 收集每个分发器的目标
    dispatcher_targets: dict[str, set[str]] = {}

    for edge in edges:
        src = edge.get("src", "")
        dst = edge.get("dst", "")

        is_disp = _is_dispatcher(src)

        # 检查自定义分发器
        if not is_disp and custom_dispatchers:
            for cd in custom_dispatchers:
                if cd in src:
                    is_disp = True
                    break

        if is_disp:
            if src not in dispatcher_targets:
                dispatcher_targets[src] = set()
            dispatcher_targets[src].add(dst)

    # 构建输出
    routes = []
    for dispatcher, targets in sorted(dispatcher_targets.items()):
        routes.append({
            "dispatcher": dispatcher,
            "targets": sorted(targets),
        })

    return {"dispatch_routes": routes}
