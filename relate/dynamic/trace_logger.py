"""
trace_logger.py — 生成 sys.settrace 回调

过滤规则：
- 只跟踪 project_root 下的文件
- 排除 site-packages、标准库
- 仅处理 "call" / "return" 事件
"""

from __future__ import annotations

import os
import sys
import sysconfig
from pathlib import Path
from typing import Callable, Optional

from relate.dynamic.trace_schema import TraceEvent


# ── 过滤规则 ────────────────────────────────────────────

# 标准库路径集合（启动时计算一次）
_STDLIB_PATHS: set[str] = set()


def _init_stdlib_paths() -> None:
    """收集标准库路径，用于排除。"""
    global _STDLIB_PATHS
    for key in ("stdlib", "platstdlib", "purelib", "platlib"):
        p = sysconfig.get_path(key)
        if p:
            _STDLIB_PATHS.add(os.path.normcase(os.path.abspath(p)))


_init_stdlib_paths()


def should_trace_file(file_path: str, project_root: Path) -> bool:
    """判断一个文件是否应该被 trace。

    规则：
    1. 必须在 project_root 下
    2. 排除 site-packages
    3. 排除标准库
    4. 排除 <frozen ...> / <string> 等特殊路径
    """
    if not file_path or file_path.startswith("<"):
        return False

    norm = os.path.normcase(os.path.abspath(file_path))
    proj = os.path.normcase(str(project_root.resolve()))

    # 必须在项目目录下
    if not norm.startswith(proj):
        return False

    # 排除 site-packages
    if "site-packages" in norm:
        return False

    # 排除标准库
    for sp in _STDLIB_PATHS:
        if norm.startswith(sp):
            return False

    return True


# ── trace 回调工厂 ──────────────────────────────────────

def make_trace_callback(
    project_root: Path,
    writer: Callable[[dict], None],
) -> Callable:
    """创建 sys.settrace 回调函数。

    Args:
        project_root: 项目根目录
        writer: 接收 dict 的写入函数（如 lambda e: append_trace_event(proj, e)）

    Returns:
        可传给 sys.settrace() 的回调
    """
    resolved_root = project_root.resolve()

    def _trace_dispatch(frame, event: str, arg):
        # 只处理 call / return
        if event not in ("call", "return"):
            return _trace_dispatch

        file_path = frame.f_code.co_filename

        if not should_trace_file(file_path, resolved_root):
            return None  # 不跟踪此 frame 的子调用

        te = TraceEvent.from_frame(frame, event)
        writer(te.to_dict())

        return _trace_dispatch

    return _trace_dispatch
