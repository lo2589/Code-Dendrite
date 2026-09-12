"""
L5_SmartAnalyzer - 统一分析入口
================================
整合所有分析层，提供智能按需分析。

主要类:
- SmartCodeAnalyzer: 统一分析器

主要函数:
- analyze_error(): 错误分析 (Hard L5-002)
- find_definition(): 查找定义 (Medium L5-003)
- trace_data(): 数据追踪 (Medium L5-004)
- on_files_changed(): 文件变更处理 (Medium L5-005)
- scan_project(): 项目扫描 (Medium L5-007)
"""

from usage.analyze.smart_analyzer.smart_analyzer import SmartCodeAnalyzer
from usage.analyze.smart_analyzer.orchestrator import (
    analyze_error,
    find_definition,
    trace_data,
    on_files_changed,
    scan_project
)

try:
    from usage.analyze.smart_analyzer.smart_analyzer_patch import SmartCodeAnalyzerV2
except Exception:
    SmartCodeAnalyzerV2 = SmartCodeAnalyzer  # 降级（Python 3.8 兼容）

__all__ = [
    'SmartCodeAnalyzer',
    'SmartCodeAnalyzerV2',
    'analyze_error',
    'find_definition',
    'trace_data',
    'on_files_changed',
    'scan_project',
]
