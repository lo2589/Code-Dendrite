"""
resolver.py - 继承链解析器 (Hard L3-003, L3-004, L3-008, L3-009)
==================================================================
核心继承链追踪逻辑。

对应TS: inheritanceResolver.ts
"""

from pathlib import PurePosixPath
from typing import List, Optional, Union, Set, Dict, Any

from base.inheritance.types import (
    ClassIndex, ClassEntry, ExternalClassEntry,
    ImportInfo, Location, MethodInfo
)
from relate.inheritance.external_lib import resolve_external_class, get_builtin_class_info

from relate.inheritance.resolver.resolve_base_class import resolve_base_class

def resolve_inheritance(
    class_name: str,
    index: ClassIndex,
    max_depth: int = 10
) -> List[Union[ClassEntry, ExternalClassEntry]]:
    """
    解析类的完整继承链 (Hard L3-003)
    
    参数:
        class_name: 类名
        index: 类索引
        max_depth: 最大追踪深度
    
    返回:
        继承链列表（从子类到根类）
    
    对应TS: inheritanceResolver.ts 的 resolveInheritanceEnhanced()
    
    核心逻辑:
        1. 从类索引中查找类
        2. 获取其基类列表
        3. 递归解析每个基类:
           - 工作区内类: 继续递归
           - 外部库类: 调用resolve_external_class
           - 内置类: 调用get_builtin_class_info
        4. 直到到达object或达到最大深度
    
    多继承处理:
        - 按顺序解析所有基类
        - 返回主继承链（第一个基类的链）
    """
    chain: List[Union[ClassEntry, ExternalClassEntry]] = []
    visited: Set[str] = set()
    
    _resolve_recursive(class_name, index, chain, visited, 0, max_depth)
    
    return chain

def _resolve_recursive(
    class_name: str,
    index: ClassIndex,
    chain: List[Union[ClassEntry, ExternalClassEntry]],
    visited: Set[str],
    depth: int,
    max_depth: int
):
    """递归解析继承链"""
    if depth >= max_depth:
        return
    
    if class_name in visited:
        return  # 避免循环
    
    visited.add(class_name)
    
    # 1. 检查工作区索引
    if class_name in index.classes:
        entry = index.classes[class_name]
        # 更新深度
        entry_copy = ClassEntry(
            name=entry.name,
            file=entry.file,
            line=entry.line,
            bases=entry.bases,
            methods=entry.methods,
            imports=entry.imports,
            depth=depth,
            is_external=False,
            module=entry.module
        )
        chain.append(entry_copy)
        
        if not entry.bases:
            # 没有基类，到达顶端
            return
        
        # 解析第一个基类（主继承链）
        base_name = entry.bases[0]
        
        # 处理Generic[T]等泛型基类
        if '[' in base_name:
            base_name = base_name.split('[')[0]
        
        resolved = resolve_base_class(base_name, entry.file, entry.imports, index)
        
        if resolved:
            if isinstance(resolved, ExternalClassEntry):
                resolved_copy = ExternalClassEntry(
                    name=resolved.name,
                    file=resolved.file,
                    line=resolved.line,
                    bases=resolved.bases,
                    module=resolved.module,
                    methods=resolved.methods
                )
                chain.append(resolved_copy)
                
                # 继续追踪外部类的基类
                if resolved.bases:
                    for base in resolved.bases:
                        _resolve_recursive(base, index, chain, visited, depth + 1, max_depth)
            else:
                _resolve_recursive(resolved.name, index, chain, visited, depth + 1, max_depth)
        else:
            # 尝试内置类
            builtin = get_builtin_class_info(base_name)
            if builtin:
                chain.append(builtin)
                if builtin.bases:
                    for base in builtin.bases:
                        _resolve_recursive(base, index, chain, visited, depth + 1, max_depth)
    
    # 2. 检查内置类
    else:
        builtin = get_builtin_class_info(class_name)
        if builtin:
            chain.append(builtin)
            if builtin.bases:
                for base in builtin.bases:
                    _resolve_recursive(base, index, chain, visited, depth + 1, max_depth)

def compute_mro(class_name: str, index: ClassIndex) -> List[str]:
    """
    计算MRO（方法解析顺序）(Hard L3-008)
    
    参数:
        class_name: 类名
        index: 类索引
    
    返回:
        MRO列表（类名字符串）
    
    实现: C3线性化算法
    
    对于多继承:
        class C(A, B): pass
        MRO = [C] + merge(mro(A), mro(B), [A, B])
    
    merge规则:
        1. 取第一个列表的第一个元素
        2. 如果该元素不在其他列表的尾部，则输出它并从所有列表中移除
        3. 否则，跳过当前列表，检查下一个
        4. 重复直到所有列表为空
    """
    # 简化实现：使用继承链
    chain = resolve_inheritance(class_name, index)
    return [entry.name for entry in chain]

def find_method_origin(
    class_name: str,
    method_name: str,
    index: ClassIndex
) -> Optional[Location]:
    """
    查找方法的原始定义位置 (Hard L3-009)
    
    参数:
        class_name: 类名
        method_name: 方法名
        index: 类索引
    
    返回:
        Location对象，未找到返回None
    
    沿MRO查找第一个定义该方法的类。
    """
    chain = resolve_inheritance(class_name, index)
    
    for entry in chain:
        for method in entry.methods:
            if method.name == method_name:
                return Location(
                    file=entry.file,
                    line=method.start_line
                )
    
    return None

def find_method_origin_with_class(
    class_name: str,
    method_name: str,
    index: ClassIndex
) -> Optional[Dict]:
    """
    查找方法定义位置（包含类名）
    
    参数:
        class_name: 类名
        method_name: 方法名
        index: 类索引
    
    返回:
        {"class": str, "file": str, "line": int}
    """
    chain = resolve_inheritance(class_name, index)
    
    for entry in chain:
        for method in entry.methods:
            if method.name == method_name:
                return {
                    "class": entry.name,
                    "file": entry.file,
                    "line": method.start_line
                }
    
    return None

def get_overridden_methods(
    class_name: str,
    index: ClassIndex
) -> List[dict]:
    """
    获取类中所有重写的方法
    
    返回:
        [{"method": str, "overrides": str, "location": Location}, ...]
    """
    if class_name not in index.classes:
        return []
    
    entry = index.classes[class_name]
    chain = resolve_inheritance(class_name, index)
    
    if len(chain) < 2:
        return []  # 没有基类
    
    result = []
    
    for method in entry.methods:
        # 检查是否在基类中定义
        for parent in chain[1:]:
            if isinstance(parent, ExternalClassEntry):
                parent_methods = [m.name for m in parent.methods] if parent.methods else []
            else:
                parent_methods = [m.name for m in parent.methods]
            
            if method.name in parent_methods:
                result.append({
                    "method": method.name,
                    "overrides": parent.name,
                    "location": Location(file=entry.file, line=method.start_line)
                })
                break
    
    return result

def find_all_subclasses(
    class_name: str,
    index: ClassIndex
) -> List[ClassEntry]:
    """
    查找类的所有子类
    
    参数:
        class_name: 类名
        index: 类索引
    
    返回:
        子类列表
    """
    subclasses = []
    
    for entry in index.classes.values():
        if class_name in entry.bases:
            subclasses.append(entry)
    
    return subclasses

def find_method_in_chain(
    chain: List[Union[ClassEntry, ExternalClassEntry]],
    method_name: str
) -> Optional[Location]:
    """
    在继承链中查找方法定义
    
    参数:
        chain: 继承链
        method_name: 方法名
    
    返回:
        方法定义位置，未找到返回 None
    """
    for entry in chain:
        for method in entry.methods:
            if method.name == method_name:
                return Location(
                    file=entry.file,
                    line=method.start_line
                )
    
    return None
