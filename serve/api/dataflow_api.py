"""
数据流分析接口层 (7 个函数)
==========================
包含 6 个直接转发 + 1 个新实现（analyze_dataflow）。
"""

from typing import Optional

from relate.dataFlow import (
    analyze_call_chain,
    trace_variable,
    get_function_inputs,
    get_function_outputs,
    get_transformations,
    generate_dataflow_html,
)
from relate.dataFlow import analyze_function_flow


# ─────────────────────────────────────────────
# 新实现：analyze_dataflow
# ─────────────────────────────────────────────

def analyze_dataflow(func: str, file: str):
    """
    分析函数的数据流（输入、输出、变换、调用链）。

    参数:
        func: 函数名（支持 "ClassName.method" 格式）
        file: 文件路径

    返回:
        FunctionDataFlow 对象，包含:
        - inputs:  输入参数列表
        - outputs: 返回值列表
        - transformations: 变量变换列表
        - calls:   函数调用列表

        分析失败返回 None
    """
    return analyze_function_flow(file, func)


__all__ = [
    # 直接转发 (6 个)
    'analyze_call_chain',
    'trace_variable',
    'get_function_inputs',
    'get_function_outputs',
    'get_transformations',
    'generate_dataflow_html',
    # 新实现 (1 个)
    'analyze_dataflow',
]
