"""
analyzer.py - 数据流分析器 (Medium L4-001, Hard L4-002, L4-003, Medium L4-006)
================================================================================
"""

import ast
from pathlib import Path
from typing import List, Optional, Dict, Set

from .types import (
    VariableInfo, Transformation, FunctionCall,
    FunctionDataFlow, VariableTrace, CallChain, CallChainStep
)


def analyze_function_flow(file_path: str, function_name: str) -> Optional[FunctionDataFlow]:
    """
    分析单个函数的数据流 (Medium L4-001)
    
    参数:
        file_path: 文件路径
        function_name: 函数名（支持 "ClassName.method" 格式）
    
    返回:
        FunctionDataFlow对象，分析失败返回None
    
    流程:
        1. 解析文件AST
        2. 找到目标函数
        3. 提取输入参数（args）
        4. 提取返回值（return语句）
        5. 提取内部变换（赋值语句）
        6. 提取函数调用
    """
    path = Path(file_path)
    if not path.exists():
        return None
    
    try:
        source = path.read_text(encoding='utf-8')
        tree = ast.parse(source)
    except (SyntaxError, OSError, UnicodeDecodeError):
        return None
    
    # 查找目标函数
    func_node = _find_function(tree, function_name)
    if not func_node:
        return None
    
    return _extract_dataflow(func_node, file_path, source)


def _find_function(tree: ast.AST, name: str):
    """在AST中查找函数"""
    parts = name.split('.')
    
    if len(parts) == 1:
        # 顶层函数
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name == name:
                    return node
    else:
        # 类方法
        class_name = parts[0]
        method_name = parts[1]
        
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and node.name == class_name:
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if item.name == method_name:
                            return item
    
    return None


def _extract_dataflow(func_node, file_path: str, source: str) -> FunctionDataFlow:
    """从函数节点提取数据流"""
    lines = source.splitlines()
    
    # 1. 提取输入参数
    inputs = []
    for arg in func_node.args.args:
        arg_type = _get_annotation_type(arg.annotation)
        inputs.append(VariableInfo(
            name=arg.arg,
            var_type=arg_type,
            source="parameter",
            line=func_node.lineno
        ))
    
    # 2. 提取返回值
    outputs = []
    if func_node.returns:
        return_type = _get_annotation_type(func_node.returns)
        outputs.append(VariableInfo(
            name="return",
            var_type=return_type,
            source="return",
            line=func_node.lineno
        ))
    
    # 3. 分析函数体
    transformations = []
    calls = []
    
    for node in ast.walk(func_node):
        # 变量赋值
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    code_snippet = _get_line(lines, node.lineno)
                    transformations.append(Transformation(
                        from_var=_get_value_source(node.value),
                        to_var=target.id,
                        operation="assignment",
                        line=node.lineno,
                        code_snippet=code_snippet
                    ))
        
        # 增强赋值（+=等）
        elif isinstance(node, ast.AugAssign):
            if isinstance(node.target, ast.Name):
                code_snippet = _get_line(lines, node.lineno)
                transformations.append(Transformation(
                    from_var=node.target.id,
                    to_var=node.target.id,
                    operation=f"aug_assign:{type(node.op).__name__}",
                    line=node.lineno,
                    code_snippet=code_snippet
                ))
        
        # 函数调用
        elif isinstance(node, ast.Call):
            call_info = _extract_call(node, lines)
            if call_info:
                calls.append(call_info)
    
    return FunctionDataFlow(
        func_id=f"{file_path}:{func_node.name}",
        file=file_path,
        line_start=func_node.lineno,
        line_end=func_node.end_lineno or func_node.lineno + 10,
        inputs=inputs,
        outputs=outputs,
        transformations=transformations,
        calls=calls
    )


def _get_annotation_type(annotation) -> str:
    """从类型注解获取类型字符串"""
    if annotation is None:
        return "Any"
    
    if isinstance(annotation, ast.Name):
        return annotation.id
    
    if isinstance(annotation, ast.Constant):
        return str(annotation.value)
    
    if isinstance(annotation, ast.Subscript):
        if isinstance(annotation.value, ast.Name):
            base = annotation.value.id
            try:
                slice_str = ast.unparse(annotation.slice)
                return f"{base}[{slice_str}]"
            except:
                return f"{base}[...]"
    
    try:
        return ast.unparse(annotation)
    except:
        return "Any"


def _get_value_source(node) -> str:
    """获取值的来源"""
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Constant):
        return f"literal:{repr(node.value)[:20]}"
    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Name):
            return f"{node.func.id}()"
        if isinstance(node.func, ast.Attribute):
            return f"{node.func.attr}()"
    if isinstance(node, ast.BinOp):
        left = _get_value_source(node.left)
        right = _get_value_source(node.right)
        return f"({left} op {right})"
    if isinstance(node, ast.List):
        return "[...]"
    if isinstance(node, ast.Dict):
        return "{...}"
    if isinstance(node, ast.Attribute):
        try:
            return ast.unparse(node)
        except:
            return f"?.{node.attr}"
    
    return "unknown"


def _extract_call(node: ast.Call, lines: List[str]) -> Optional[FunctionCall]:
    """提取函数调用信息"""
    # 获取被调用函数名
    if isinstance(node.func, ast.Name):
        func_name = node.func.id
    elif isinstance(node.func, ast.Attribute):
        func_name = node.func.attr
    else:
        return None
    
    # 获取参数
    args = []
    for arg in node.args:
        if isinstance(arg, ast.Name):
            args.append(arg.id)
        elif isinstance(arg, ast.Constant):
            args.append(repr(arg.value)[:20])
        else:
            try:
                args.append(ast.unparse(arg)[:30])
            except:
                args.append("?")
    
    code_snippet = _get_line(lines, node.lineno)
    
    return FunctionCall(
        target=func_name,
        args=args,
        line=node.lineno,
        code_snippet=code_snippet,
        return_var=None
    )


def _get_line(lines: List[str], lineno: int) -> str:
    """获取指定行代码"""
    if 1 <= lineno <= len(lines):
        return lines[lineno - 1].strip()
    return ""


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


def _build_func_index(project_info: Dict) -> Dict[str, Dict]:
    """构建函数索引"""
    all_funcs = {}
    
    for mod in project_info.get('modules', []):
        for feat in mod.get('features', []):
            for fn in feat.get('functions', []):
                if 'id' in fn:
                    all_funcs[fn['id']] = fn
    
    return all_funcs


def _find_next_function(
    flow: FunctionDataFlow,
    all_funcs: Dict[str, Dict],
    project_info: Dict
) -> Optional[str]:
    """找到调用链中的下一个函数"""
    if not flow.calls:
        return None
    
    # 尝试找第一个在项目中的调用
    for call in flow.calls:
        target = call.target
        
        # 在函数索引中查找
        for func_id, func_info in all_funcs.items():
            if func_info.get('name') == target:
                return func_id
    
    # 检查call_graph
    call_graph = project_info.get('call_graph', {})
    if flow.func_id in call_graph:
        calls = call_graph[flow.func_id].get('calls', [])
        for call_id in calls:
            if call_id in all_funcs:
                return call_id
    
    return None


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
