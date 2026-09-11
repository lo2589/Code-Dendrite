"""
analyzer.py - 数据流分析器 (Medium L4-001, Hard L4-002, L4-003, Medium L4-006)
================================================================================
"""

import ast
from pathlib import Path
from typing import List, Optional, Dict, Set

from base.dataFlow.types import (
    VariableInfo, Transformation, FunctionCall,
    FunctionDataFlow, VariableTrace, CallChain, CallChainStep
)

from relate.dataFlow.analyzer.analyze_function_flow import _build_func_index, _get_line, _extract_call, _extract_dataflow, _get_annotation_type, _get_value_source, _find_function, _find_next_function, analyze_function_flow
from relate.dataFlow.analyzer.function import analyze_call_chain, get_function_calls, get_function_inputs, get_function_outputs, get_transformations, trace_variable

__all__ = ['_build_func_index', '_get_line', '_extract_call', '_extract_dataflow', '_get_annotation_type', '_get_value_source', '_find_function', '_find_next_function', 'analyze_function_flow', 'analyze_call_chain', 'get_function_calls', 'get_function_inputs', 'get_function_outputs', 'get_transformations', 'trace_variable']
