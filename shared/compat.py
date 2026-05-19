"""
shared/compat.py - CodeDendrite 跨平台兼容层
============================================

提供路径标准化、编码处理等跨平台兼容性工具。

功能：
1. 路径标准化 - 统一使用正斜杠（跨系统兼容）
2. 路径比较 - 忽略分隔符差异
3. 编码安全 - UTF-8处理

使用方式:
    from shared.compat import normalize_path
    path = normalize_path("smartAnalyzer\\orchestrator.py")
    # → "smartAnalyzer/orchestrator.py"
"""

import os
import sys
from pathlib import Path
from typing import Union


# ── 路径标准化 ──────────────────────────────────────────────

def normalize_path(path: Union[str, Path]) -> str:
    """
    将路径转换为统一的正斜杠格式（跨系统兼容）
    
    Windows: "smartAnalyzer\\orchestrator.py" → "smartAnalyzer/orchestrator.py"
    Linux/Mac: "smartAnalyzer/orchestrator.py" → "smartAnalyzer/orchestrator.py"
    
    这是解决跨系统兼容性问题的核心函数。
    """
    return str(path).replace("\\", "/")


def path_matches(path1: Union[str, Path], path2: Union[str, Path]) -> bool:
    """
    比较两个路径是否相同（忽略分隔符差异）
    
    示例:
        path_matches("api/anchors.py", "api\\anchors.py")  # True
        path_matches("api/anchors.py", "api/anchors.py")  # True
    """
    return normalize_path(path1) == normalize_path(path2)


# ── 导出（供其他模块使用）───────────────────────────────────

__all__ = [
    "normalize_path",
    "path_matches",
]
