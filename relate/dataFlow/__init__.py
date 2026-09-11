"""
L4_DataFlow - 动态数据流分析系统
==================================
对现有dataflow_analyzer.py的封装和增强，提供更易用的接口。

主要函数:
- analyze_function_flow(): 分析单个函数的数据流 (Medium L4-001)
- trace_variable(): 追踪变量流动 (Hard L4-002)
- analyze_call_chain(): 分析调用链 (Hard L4-003)
- get_function_inputs(): 获取函数输入 (Easy L4-004)
- get_function_outputs(): 获取函数输出 (Easy L4-005)
- get_transformations(): 获取变量变换 (Medium L4-006)
- generate_dataflow_html(): 生成HTML可视化 (Easy L4-007)
"""

from base.dataFlow.types import (
    VariableInfo, Transformation, FunctionCall,
    FunctionDataFlow, VariableTrace, CallChain, CallChainStep
)
from relate.dataFlow.analyzer import (
    analyze_function_flow,
    trace_variable,
    analyze_call_chain,
    get_function_inputs,
    get_function_outputs,
    get_transformations
)
from relate.dataFlow.visualizer import generate_dataflow_html

__all__ = [
    # 类型
    'VariableInfo',
    'Transformation',
    'FunctionCall',
    'FunctionDataFlow',
    'VariableTrace',
    'CallChain',
    'CallChainStep',
    # 函数
    'analyze_function_flow',
    'trace_variable',
    'analyze_call_chain',
    'get_function_inputs',
    'get_function_outputs',
    'get_transformations',
    'generate_dataflow_html',
]
