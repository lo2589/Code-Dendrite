"""
项目扫描接口层 (8 个函数)
========================
转发到 smartAnalyzer.orchestrator 的模块级函数。
"""

from smartAnalyzer.orchestrator import (
    scan_project,
    on_files_changed,
    analyze_error,
    find_definition,
    trace_data,
    get_cache_stats,
    clear_cache,
)

__all__ = [
    'scan_project',
    'on_files_changed',
    'analyze_error',
    'find_definition',
    'trace_data',
    'get_cache_stats',
    'clear_cache',
]
