"""
CodeDendrite Dynamic Analysis — 补齐静态分析盲区

模块：
  trace_schema     - TraceEvent 数据结构
  dynamic_store    - 读写 JSONL / JSON 存储
  trace_logger     - sys.settrace 回调生成
  trace_runner     - 执行带 trace 的脚本
  edge_extractor   - 从 trace 事件提取执行边
  route_mapper     - 从执行边提取路由映射
  merge            - 静态图融合动态数据（只读）
  trace_cli        - CLI 入口

用法：
  # CLI
  python -m dynamic.trace_cli trace --project . --script test.py
  python -m dynamic.trace_cli edges --project .
  python -m dynamic.trace_cli routes --project .

  # API
  from relate.dynamic import run_with_trace, extract_executed_edges, extract_dispatch_routes
"""

from relate.dynamic.trace_schema import TraceEvent
from relate.dynamic.dynamic_store import (
    get_dynamic_dir,
    append_trace_event,
    iter_trace_events,
    save_executed_edges,
    load_executed_edges,
    save_routes,
    load_routes,
    clear_trace_events,
)
from relate.dynamic.trace_logger import should_trace_file, make_trace_callback
from relate.dynamic.trace_runner import run_with_trace
from relate.dynamic.edge_extractor import extract_executed_edges
from relate.dynamic.route_mapper import extract_dispatch_routes
from relate.dynamic.merge import merge_static_with_executed

__all__ = [
    "TraceEvent",
    "get_dynamic_dir",
    "append_trace_event",
    "iter_trace_events",
    "save_executed_edges",
    "load_executed_edges",
    "save_routes",
    "load_routes",
    "clear_trace_events",
    "should_trace_file",
    "make_trace_callback",
    "run_with_trace",
    "extract_executed_edges",
    "extract_dispatch_routes",
    "merge_static_with_executed",
]
