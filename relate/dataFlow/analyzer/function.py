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

from relate.dataFlow.analyzer.analyze_function_flow import _build_func_index, _find_next_function, analyze_function_flow

def analyze_call_chain(
    entry_point: str,
    project_info: Dict,
    max_depth: int = 10
) -> Optional[CallChain]:
    """
    分析调用链 (Hard L4-003)
    
    参数:
        entry_point: 入口函数ID（格式: "file_path:function_name"）
        project_info: 项目信息字典（需包含modules和call_graph）
        max_depth: 最大追踪深度
    
    返回:
        CallChain对象
    """
    # 解析入口点
    if ':' in entry_point:
        file_path, func_name = entry_point.rsplit(':', 1)
    else:
        return None
    
    # 构建函数索引
    all_funcs = _build_func_index(project_info)
    
    steps = []
    visited: Set[str] = set()
    current_func = entry_point
    step_index = 0
    
    while current_func and step_index < max_depth:
        if current_func in visited:
            break
        visited.add(current_func)
        
        # 解析当前函数
        if ':' in current_func:
            f_path, f_name = current_func.rsplit(':', 1)
        else:
            break
        
        flow = analyze_function_flow(f_path, f_name)
        if not flow:
            break
        
        step = CallChainStep(
            step_index=step_index,
            function=current_func,
            file=f_path,
            line=flow.line_start,
            inputs=[i.to_dict() for i in flow.inputs],
            outputs=[o.to_dict() for o in flow.outputs],
            transformations=[t.to_dict() for t in flow.transformations],
            next_function=None
        )
        
        # 找下一个函数
        next_func = _find_next_function(flow, all_funcs, project_info)
        if next_func:
            step.next_function = next_func
            current_func = next_func
            step_index += 1
        else:
            current_func = None
        
        steps.append(step)
    
    if not steps:
        return None
    
    return CallChain(
        entry_point=entry_point,
        depth=len(steps),
        steps=steps
    )

def get_function_calls(file_path: str, function_name: str) -> List[FunctionCall]:
    """
    获取函数内的所有调用
    
    参数:
        file_path: 文件路径
        function_name: 函数名
    
    返回:
        函数调用列表
    """
    flow = analyze_function_flow(file_path, function_name)
    return flow.calls if flow else []

def get_function_inputs(file_path: str, function_name: str) -> List[VariableInfo]:
    """
    获取函数输入参数 (Easy L4-004)
    
    参数:
        file_path: 文件路径
        function_name: 函数名
    
    返回:
        输入参数列表
    """
    flow = analyze_function_flow(file_path, function_name)
    return flow.inputs if flow else []

def get_function_outputs(file_path: str, function_name: str) -> List[VariableInfo]:
    """
    获取函数返回值 (Easy L4-005)
    
    参数:
        file_path: 文件路径
        function_name: 函数名
    
    返回:
        返回值列表
    """
    flow = analyze_function_flow(file_path, function_name)
    return flow.outputs if flow else []

def get_transformations(file_path: str, function_name: str) -> List[Transformation]:
    """
    获取函数内的变量变换 (Medium L4-006)
    
    参数:
        file_path: 文件路径
        function_name: 函数名
    
    返回:
        变量变换列表
    """
    flow = analyze_function_flow(file_path, function_name)
    return flow.transformations if flow else []

def trace_variable(
    file_path: str,
    function_name: str,
    variable_name: str
) -> Optional[VariableTrace]:
    """
    追踪变量在函数中的流动 (Hard L4-002)
    
    参数:
        file_path: 文件路径
        function_name: 函数名
        variable_name: 变量名
    
    返回:
        VariableTrace对象，分析失败返回None
    
    流程:
        1. 解析函数
        2. 找到变量的定义位置
        3. 追踪所有对该变量的变换
        4. 找到变量的最终使用
    """
    flow = analyze_function_flow(file_path, function_name)
    if not flow:
        return None
    
    # 找变量来源
    origin = None
    
    # 检查输入参数
    for inp in flow.inputs:
        if inp.name == variable_name:
            origin = inp
            break
    
    if not origin:
        # 检查内部变量（被赋值的变量）
        for trans in flow.transformations:
            if trans.to_var == variable_name:
                origin = VariableInfo(
                    name=variable_name,
                    var_type="Any",
                    source=trans.from_var,
                    line=trans.line
                )
                break
    
    if not origin:
        return None
    
    # 收集变换
    var_transformations = []
    current_var = variable_name
    
    for trans in sorted(flow.transformations, key=lambda t: t.line):
        if trans.from_var == current_var or trans.to_var == current_var:
            var_transformations.append(trans)
            if trans.to_var != current_var:
                current_var = trans.to_var
    
    # 找最终使用（传给了哪些函数）
    passed_to = []
    for call in flow.calls:
        if variable_name in call.args:
            passed_to.append(call.target)
    
    # 找最终使用位置
    final_usage = []
    for call in flow.calls:
        if variable_name in call.args:
            final_usage.append(f"{call.target}() at line {call.line}")
    
    return VariableTrace(
        variable_name=variable_name,
        origin=origin,
        transformations=var_transformations,
        final_usage=final_usage,
        passed_to=passed_to
    )
