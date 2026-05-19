"""
继承追踪接口层 (12 个函数)
==========================
包含 11 个直接转发 + 1 个新实现（trace_inheritance）。
"""

from typing import Optional, List, Dict, Any

from inheritance import (
    find_subclasses,
    analyze_super_calls,
    build_override_chain,
    resolve_external_class,
    InheritanceTracker,
    create_tracker,
    parse_python_file,
    build_class_index,
    resolve_inheritance,
    compute_mro,
    find_method_origin,
)


# ─────────────────────────────────────────────
# 新实现：trace_inheritance
# ─────────────────────────────────────────────

def trace_inheritance(
    class_name: str,
    method: str = None,
    root: str = ".",
) -> Dict[str, Any]:
    """
    追踪类的继承链，可选追踪特定方法来源。

    参数:
        class_name: 类名
        method: 方法名（可选）。指定后追踪该方法在继承链中的定义位置
        root: 项目根目录

    返回:
        {
            "class_name": str,
            "mro": [str],              # 方法解析顺序
            "chain": [dict],           # 完整继承链
            "depth": int,              # 继承深度
            "method_origin": dict|None # 方法定义位置（仅在指定 method 时返回）
        }
    """
    tracker = InheritanceTracker(root)

    result = tracker.export_chain_as_dict(class_name)

    if method:
        origin = tracker.find_method_origin(class_name, method)
        result["method_origin"] = origin

    return result


__all__ = [
    # 直接转发 (11 个)
    'find_subclasses',
    'analyze_super_calls',
    'build_override_chain',
    'resolve_external_class',
    'InheritanceTracker',
    'create_tracker',
    'parse_python_file',
    'build_class_index',
    'resolve_inheritance',
    'compute_mro',
    'find_method_origin',
    # 新实现 (1 个)
    'trace_inheritance',
]
