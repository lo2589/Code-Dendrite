"""
智能分析接口层 (1 个函数)
========================
包装 SmartCodeAnalyzer 提供独立函数接口。
"""

from typing import Optional, Dict


def smart_analyze(
    error: str,
    file: str = None,
    severity: str = "high",
    root: str = ".",
) -> Dict:
    """
    智能分析错误，自动选择分析深度。

    参数:
        error: 错误信息
        file: 相关文件路径（可选）
        severity: 严重程度 ("low"|"medium"|"high"|"critical")，决定启用哪些分析层
        root: 项目根目录

    返回:
        AnalysisReport 对象，包含:
        - target:       分析目标
        - findings:     各层发现的问题列表
        - suggestions:  修复建议列表
        - layers_used:  使用的分析层
        - elapsed_ms:   耗时
    """
    from synth.smartAnalyzer.orchestrator import analyze_error
    return analyze_error(
        error_msg=error,
        file_path=file,
        severity=severity,
        root=root,
    )


__all__ = [
    'smart_analyze',
]
