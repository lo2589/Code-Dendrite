"""
trace_runner.py — 执行带 trace 的 Python 程序

流程：
1. 清空旧 trace 数据
2. 设置 sys.settrace
3. 执行目标脚本
4. finally 关闭 trace
"""

from __future__ import annotations

import sys
import runpy
from pathlib import Path
from typing import Optional

from relate.dynamic.dynamic_store import append_trace_event, clear_trace_events
from relate.dynamic.trace_logger import make_trace_callback


def run_with_trace(
    project_root: str,
    script_path: str,
    script_args: Optional[list[str]] = None,
    clear_old: bool = True,
) -> None:
    """带 trace 运行一个 Python 脚本。

    Args:
        project_root: 项目根目录
        script_path: 要执行的 .py 文件路径
        script_args: 传给脚本的命令行参数
        clear_old: 是否清空旧 trace 数据
    """
    proj = str(Path(project_root).resolve())

    if clear_old:
        clear_trace_events(proj)

    # 构建写入器
    def writer(event_dict: dict) -> None:
        append_trace_event(proj, event_dict)

    # 构建 trace 回调
    callback = make_trace_callback(Path(proj), writer)

    # 设置 sys.argv（脚本可能依赖）
    old_argv = sys.argv[:]
    sys.argv = [script_path] + (script_args or [])

    # 将脚本所在目录加入 sys.path
    script_dir = str(Path(script_path).resolve().parent)
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)

    try:
        sys.settrace(callback)
        # 用 runpy 执行脚本，模拟 python xxx.py
        runpy.run_path(
            str(Path(script_path).resolve()),
            run_name="__main__",
        )
    except SystemExit:
        pass  # 脚本自己 sys.exit() 是正常的
    except Exception as e:
        print(f"[trace_runner] Script raised: {type(e).__name__}: {e}", file=sys.stderr)
    finally:
        sys.settrace(None)
        sys.argv = old_argv
