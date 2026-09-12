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

from scanner.calls.string_dispatch.extract_called_symbols import _attach_parents, _build_dispatch_edge, _build_function_id, _extract_called_symbols, _extract_compare_parts, _find_enclosing_class, _is_elif_node, _is_string_compare, _walk_if_chain

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

def find_string_dispatches(root: str) -> List[Dict]:
    """
    扫描项目根目录下所有 Python 文件，提取 dispatch 边。
    
    Args:
        root: 项目根目录
        
    Returns:
        dispatch edge dict 列表
    """
    try:
        from analyzer.shared.codedendrite_ignore import CodeDendriteIgnore
    except ImportError:
        from analyzer.shared.codedendrite_ignore import CodeDendriteIgnore

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
