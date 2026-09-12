"""
trace_schema.py — 统一事件结构

TraceEvent 封装一次 call/return 事件，
提供 from_frame() 快速从 Python frame 构造。
"""

from __future__ import annotations

import time
from dataclasses import dataclass, asdict
from typing import Optional


@dataclass(slots=True)
class TraceEvent:
    event: str                          # "call" | "return"
    ts: float                           # time.time()
    file: str                           # 绝对路径
    line: int
    func_name: str                      # 函数名
    qualname: str                       # 限定名 (Class.method)
    caller_file: Optional[str] = None
    caller_line: Optional[int] = None
    caller_qualname: Optional[str] = None

    # ── 序列化 ──────────────────────────────────────────

    def to_dict(self) -> dict:
        return asdict(self)

    # ── 从 frame 构造 ──────────────────────────────────

    @staticmethod
    def from_frame(frame, event: str) -> TraceEvent:
        """从 sys.settrace 回调的 frame + event 构造 TraceEvent。

        不记录参数、不记录 locals。
        """
        code = frame.f_code
        caller = frame.f_back

        caller_file: Optional[str] = None
        caller_line: Optional[int] = None
        caller_qualname: Optional[str] = None

        if caller is not None:
            caller_code = caller.f_code
            caller_file = caller_code.co_filename
            caller_line = caller.f_lineno
            # qualname: 优先用 co_qualname (3.11+), fallback co_name
            caller_qualname = getattr(
                caller_code, "co_qualname", caller_code.co_name
            )

        return TraceEvent(
            event=event,
            ts=time.time(),
            file=code.co_filename,
            line=frame.f_lineno,
            func_name=code.co_name,
            qualname=getattr(code, "co_qualname", code.co_name),
            caller_file=caller_file,
            caller_line=caller_line,
            caller_qualname=caller_qualname,
        )
