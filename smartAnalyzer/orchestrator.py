"""
orchestrator.py - 模块级函数封装
=================================
提供便捷的函数式接口。
"""

from pathlib import Path
from typing import Dict, List, Optional

from shared.types import AnalysisReport, ScanResult


# 全局分析器实例缓存
_analyzers: Dict[str, 'SmartCodeAnalyzer'] = {}


def _get_analyzer(root: str):
    """获取或创建分析器实例"""
    if root not in _analyzers:
        from .smart_analyzer import SmartCodeAnalyzer
        _analyzers[root] = SmartCodeAnalyzer(root)
    return _analyzers[root]


def analyze_error(
    error_msg: str,
    file_path: Optional[str] = None,
    severity: str = "medium",
    root: str = "."
) -> AnalysisReport:
    """
    分析错误 (Hard L5-002)
    
    参数:
        error_msg: 错误信息
        file_path: 相关文件路径
        severity: 严重程度 ("low" | "medium" | "high" | "critical")
        root: 项目根目录
    
    返回:
        AnalysisReport对象
    
    使用示例:
        report = analyze_error(
            "TypeError: 'NoneType' object is not callable",
            file_path="backend/main.py",
            severity="high"
        )
    """
    analyzer = _get_analyzer(root)
    return analyzer.analyze_error(error_msg, file_path, severity)


def find_definition(
    symbol: str,
    file_path: str,
    root: str = "."
) -> Optional[Dict]:
    """
    查找符号定义位置 (Medium L5-003)
    
    参数:
        symbol: 符号名（如 "ClassName" 或 "ClassName.method"）
        file_path: 当前文件路径
        root: 项目根目录
    
    返回:
        {
            "symbol": str,
            "file": str,
            "line": int,
            "type": "class" | "method" | "function"
        }
        未找到返回None
    
    使用示例:
        location = find_definition("SmartRouter", "backend/main.py")
        if location:
            print(f"定义在 {location['file']}:{location['line']}")
    """
    analyzer = _get_analyzer(root)
    return analyzer.find_definition(symbol, file_path)


def trace_data(
    variable: str,
    function: str,
    file_path: str,
    root: str = "."
) -> Optional[Dict]:
    """
    追踪变量数据流 (Medium L5-004)
    
    参数:
        variable: 变量名
        function: 函数名
        file_path: 文件路径
        root: 项目根目录
    
    返回:
        变量追踪结果字典
    
    使用示例:
        trace = trace_data("request", "handle_chat", "backend/main.py")
        if trace:
            print(f"变量来源: {trace['origin']}")
            print(f"传递给: {trace['passed_to']}")
    """
    analyzer = _get_analyzer(root)
    return analyzer.trace_data(variable, function, file_path)


def on_files_changed(
    changed_files: List[str],
    root: str = ".",
    include_virtual_blocks: bool = False,
) -> Dict:
    """
    处理文件变更 (Medium L5-005)
    
    参数:
        changed_files: 变更的文件列表
        root: 项目根目录
    
    返回:
        处理结果字典
    
    设计原则:
        - 同步执行，秒级完成
        - 只处理变更文件相关的锚点
    
    使用示例:
        result = on_files_changed(["backend/main.py", "backend/config.py"])
        print(f"更新了 {result['anchors']['updated']} 个锚点")
    """
    analyzer = _get_analyzer(root)
    return analyzer.on_files_changed(
        changed_files,
        include_virtual_blocks=include_virtual_blocks,
    )


def scan_project(
    incremental: bool = True,
    root: str = "."
) -> ScanResult:
    """
    扫描项目 (Medium L5-007)
    
    参数:
        incremental: 是否增量扫描
        root: 项目根目录
    
    返回:
        ScanResult对象
    
    使用示例:
        result = scan_project()
        print(f"扫描了 {result.scanned_files} 个文件")
        print(f"发现 {result.classes_count} 个类")
    """
    analyzer = _get_analyzer(root)
    return analyzer.scan_project(incremental)


def get_cache_stats(root: str = ".") -> Dict:
    """
    获取缓存统计 (Easy L5-006)
    
    参数:
        root: 项目根目录
    
    返回:
        各层缓存统计
    """
    analyzer = _get_analyzer(root)
    stats = analyzer.get_cache_stats()
    return {name: s.to_dict() for name, s in stats.items()}


def clear_cache(root: str = "."):
    """清除所有缓存"""
    if root in _analyzers:
        analyzer = _analyzers[root]
        analyzer._cache.clear_all()
        analyzer._class_index = None
