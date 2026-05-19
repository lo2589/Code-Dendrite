"""
string_dispatch.py — 字符串路由边提取
====================================
扫描 Python AST，提取 if/elif 字符串比较条件下的调用关系。

支持的语法：
- if method == "xxx": self._handle_xxx(...)
- elif action == "yyy": await self._handle_yyy(...)
- return self.handler(...)

不支持的语法（本次不做）：
- match/case
- dict dispatch
- in / not in
- and / or 组合条件
"""

import ast
import os
from pathlib import Path
from typing import List, Dict, Optional, Tuple


def find_string_dispatches(root: str) -> List[Dict]:
    """
    扫描项目根目录下所有 Python 文件，提取 dispatch 边。
    
    Args:
        root: 项目根目录
        
    Returns:
        dispatch edge dict 列表
    """
    try:
        from shared.codedendrite_ignore import CodeDendriteIgnore
    except ImportError:
        from tools.CodeDendrite.shared.codedendrite_ignore import CodeDendriteIgnore

    ignore = CodeDendriteIgnore(root)
    root_path = Path(root)
    edges = []
    for dirpath, dirnames, filenames in os.walk(root):
        dp = Path(dirpath)
        dirnames[:] = [d for d in dirnames if ignore.should_scan(dp / d / "_x.py")]

        for fname in filenames:
            if not fname.endswith('.py'):
                continue
            fp = dp / fname
            if not ignore.should_scan(fp):
                continue
            try:
                edges.extend(extract_dispatches_from_file(str(fp), root))
            except Exception as ex:
                print(f"[string_dispatch] 跳过文件 {fp}: {ex}")
    return edges


def extract_dispatches_from_file(file_path: str, root: str = ".") -> List[Dict]:
    """
    提取单个 Python 文件中的 dispatch 边。
    
    Args:
        file_path: Python 文件绝对路径
        root: 项目根目录（用于生成相对路径）
        
    Returns:
        当前文件里的 dispatch edges
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            source = f.read()
        tree = ast.parse(source, filename=str(file_path))
        _attach_parents(tree)
    except Exception:
        # 文件读失败或 parse 失败，返回空列表
        return []
    
    # 计算相对路径
    rel_path = os.path.relpath(file_path, root).replace('\\', '/')
    
    edges = []
    
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # 查找所属类（如果有）
            class_name = _find_enclosing_class(tree, node)
            func_edges = extract_dispatches_from_function(node, rel_path, class_name)
            edges.extend(func_edges)
    
    return edges


def extract_dispatches_from_function(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    file_path: str,
    class_name: Optional[str] = None
) -> List[Dict]:
    """
    提取单个函数中的 dispatch 边。
    
    Args:
        node: ast.FunctionDef 或 ast.AsyncFunctionDef
        file_path: 文件相对路径
        class_name: 所在类名，没有则为 None
        
    Returns:
        当前函数里的 dispatch edges
    """
    _attach_parents(node)
    edges = []
    from_id = _build_function_id(file_path, class_name, node.name)
    
    # 递归遍历所有子节点找 if 语句（可能在 try/with 等块内）
    for child in ast.walk(node):
        if not isinstance(child, ast.If):
            continue
        if _is_elif_node(child):
            continue
        
        # 展开 if/elif 链
        for condition, body in _walk_if_chain(child):
            # 检查是否是字符串比较条件
            if not _is_string_compare(condition):
                continue
            
            # 提取条件信息
            dispatch_key, dispatch_value, condition_str = _extract_compare_parts(condition)
            if not dispatch_key or not dispatch_value:
                continue
            
            # 提取 body 中的调用目标
            called_symbols = _extract_called_symbols(body)
            
            for symbol in called_symbols:
                edge = _build_dispatch_edge(
                    from_id=from_id,
                    to_symbol=symbol,
                    condition=condition_str,
                    dispatch_key=dispatch_key,
                    dispatch_value=dispatch_value,
                    file_path=file_path,
                    class_name=class_name
                )
                if edge:
                    edges.append(edge)
    
    return edges


def _find_enclosing_class(tree: ast.AST, target_node: ast.AST) -> Optional[str]:
    """查找目标节点所在的类名。"""
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for child in ast.iter_child_nodes(node):
                if child is target_node:
                    return node.name
    return None


def _attach_parents(tree: ast.AST) -> None:
    """为 AST 节点标记父节点，便于识别 elif 分支。"""
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            setattr(child, "_codedendrite_parent", parent)


def _is_elif_node(node: ast.If) -> bool:
    """判断当前 if 节点是否是 if/elif 链中的 elif 节点。"""
    parent = getattr(node, "_codedendrite_parent", None)
    return isinstance(parent, ast.If) and node in parent.orelse


def _is_string_compare(test: ast.AST) -> bool:
    """
    判断是否是字符串比较条件。
    
    识别模式：
    - method == "chat_message"
    - action == "scan"
    - kind == "query"
    """
    if not isinstance(test, ast.Compare):
        return False
    
    # 只处理单一比较（不支持 and/or 组合）
    if len(test.ops) != 1 or len(test.comparators) != 1:
        return False
    
    op = test.ops[0]
    if not isinstance(op, ast.Eq):
        return False
    
    # 右边必须是字符串常量
    right = test.comparators[0]
    if not isinstance(right, ast.Constant) or not isinstance(right.value, str):
        return False
    
    # 左边可以是 Name 或 Attribute
    left = test.left
    if isinstance(left, ast.Name):
        return True
    if isinstance(left, ast.Attribute):
        return True
    
    return False


def _extract_compare_parts(test: ast.AST) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """
    提取比较条件的各部分。
    
    Args:
        test: ast.Compare 节点
        
    Returns:
        (dispatch_key, dispatch_value, condition)
        
    Example:
        method == "chat_message"
        -> ("method", "chat_message", 'method == "chat_message"')
    """
    if not isinstance(test, ast.Compare):
        return None, None, None
    
    left = test.left
    right = test.comparators[0]
    
    # 提取 dispatch_key
    if isinstance(left, ast.Name):
        dispatch_key = left.id
    elif isinstance(left, ast.Attribute):
        dispatch_key = left.attr
    else:
        return None, None, None
    
    # 提取 dispatch_value
    if isinstance(right, ast.Constant) and isinstance(right.value, str):
        dispatch_value = right.value
    else:
        return None, None, None
    
    # 构建条件字符串
    condition = f'{dispatch_key} == "{dispatch_value}"'
    
    return dispatch_key, dispatch_value, condition


def _extract_called_symbols(body: List[ast.stmt]) -> List[str]:
    """
    提取 if/elif body 中的调用目标。
    
    支持形态：
    - self._handle_xxx(...)
    - await self._handle_xxx(...)
    - return self._handle_xxx(...)
    - return await self._handle_xxx(...)
    - obj.run(...)
    
    Args:
        body: if/elif 的 body 语句列表
        
    Returns:
        调用目标符号列表
    """
    symbols = []
    
    for stmt in body:
        call_node = None
        
        # 直接调用
        if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
            call_node = stmt.value
        
        # return 调用
        elif isinstance(stmt, ast.Return) and stmt.value:
            if isinstance(stmt.value, ast.Call):
                call_node = stmt.value
            # return await 调用
            elif isinstance(stmt.value, ast.Await) and isinstance(stmt.value.value, ast.Call):
                call_node = stmt.value.value
        
        # await 调用（Expr + Await + Call）
        elif isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Await):
            if isinstance(stmt.value.value, ast.Call):
                call_node = stmt.value.value
        
        if call_node:
            symbol = _extract_call_target(call_node)
            if symbol:
                symbols.append(symbol)
    
    return symbols


def _extract_call_target(call_node: ast.Call) -> Optional[str]:
    """
    从 Call 节点提取调用目标符号。
    
    Args:
        call_node: ast.Call 节点
        
    Returns:
        符号字符串，如 "self._handle_chat_with_model" 或 "handler.run"
    """
    func = call_node.func
    
    # self.xxx 或 obj.xxx
    if isinstance(func, ast.Attribute):
        if isinstance(func.value, ast.Name):
            return f"{func.value.id}.{func.attr}"
        # self.obj.xxx（嵌套属性）
        elif isinstance(func.value, ast.Attribute):
            # 最多支持两层
            if isinstance(func.value.value, ast.Name):
                return f"{func.value.value.id}.{func.value.attr}.{func.attr}"
    
    # 直接函数调用（非方法）
    elif isinstance(func, ast.Name):
        return func.id
    
    return None


def _build_dispatch_edge(
    from_id: str,
    to_symbol: str,
    condition: str,
    dispatch_key: str,
    dispatch_value: str,
    file_path: str,
    class_name: Optional[str] = None
) -> Optional[Dict]:
    """
    构建 dispatch 边字典。
    
    Args:
        from_id: 源函数 ID
        to_symbol: 目标调用符号
        condition: 条件表达式
        dispatch_key: 分发键
        dispatch_value: 分发值
        file_path: 文件路径
        class_name: 类名
        
    Returns:
        dispatch edge dict
    """
    # 构建 to_id
    # to_symbol 可能是 "self._handle_xxx" 或 "handler.run"
    # 需要转换为 file::symbol 格式
    
    parts = to_symbol.split('.')

    # 如果是 self.xxx，且当前在类中，则 to_id 为 class.method
    if parts[0] == 'self' and class_name:
        method_name = parts[-1]
        to_id = f"{file_path}::{class_name}.{method_name}"
    else:
        to_id = f"{file_path}::{to_symbol}"
    
    return {
        "from_id": from_id,
        "to_id": to_id,
        "edge_type": "dispatch",
        "condition": condition,
        "dispatch_key": dispatch_key,
        "dispatch_value": dispatch_value,
        "is_conditional": True,
        "data_in": "string route",
        "data_out": "conditional call",
        "source_file": file_path,
    }


def _build_function_id(file_path: str, class_name: Optional[str], func_name: str) -> str:
    """
    构建函数 ID，与现有 anchors/relations 格式保持一致。
    
    Args:
        file_path: 文件相对路径
        class_name: 类名（可选）
        func_name: 函数名
        
    Returns:
        函数 ID，格式为 "file::Class.method" 或 "file::function"
    """
    if class_name:
        return f"{file_path}::{class_name}.{func_name}"
    return f"{file_path}::{func_name}"


def _walk_if_chain(if_node: ast.If) -> List[Tuple[ast.AST, List[ast.stmt]]]:
    """
    展开 if/elif 链。
    
    Args:
        if_node: ast.If 节点
        
    Returns:
        [(condition, body), ...] 列表
    """
    chain = []
    current = if_node
    
    while current:
        chain.append((current.test, current.body))
        
        # 检查 orelse 是否是 elif
        if current.orelse and len(current.orelse) == 1 and isinstance(current.orelse[0], ast.If):
            current = current.orelse[0]
        else:
            break
    
    return chain


__all__ = [
    "find_string_dispatches",
    "extract_dispatches_from_file",
    "extract_dispatches_from_function",
]
