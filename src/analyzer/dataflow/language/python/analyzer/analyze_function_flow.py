"""
analyzer.py - 数据流分析器 (Medium L4-001, Hard L4-002, L4-003, Medium L4-006)
================================================================================
"""

import ast
from pathlib import Path
from typing import List, Optional, Dict, Set

from analyzer.shared.legacy.dataFlow.types import (
    VariableInfo, Transformation, FunctionCall,
    FunctionDataFlow, VariableTrace, CallChain, CallChainStep
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

def _get_line(lines: List[str], lineno: int) -> str:
    """获取指定行代码"""
    if 1 <= lineno <= len(lines):
        return lines[lineno - 1].strip()
    return ""

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
